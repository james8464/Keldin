# Run subject-family hooks through shared authoring, validation and rendering steps.

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unicodedata import normalize

from Backend.Core.ai_assessment import (
    ASSESSMENT_REVIEW_VERSION,
    GenerationPolicy,
    generate_unique_paper,
)
from Backend.Core.assessment_checkpoints import (
    AssessmentCheckpointStore,
    identity_for_blueprint,
)
from Backend.Core.assessment_package import write_assessment_package
from Backend.Core.document_publication import publish_document_set
from Backend.Core.family_contracts import ArtifactSpec as ArtifactSpec
from Backend.Core.family_contracts import BuildResult as BuildResult
from Backend.Core.family_contracts import FamilyAdapter as FamilyAdapter
from Backend.Core.family_contracts import ProgressCallback as ProgressCallback
from Backend.Core.json_client import JSONGenerationClient
from Backend.Core.model_recommendations import default_ollama_model
from Backend.Core.numeric_integrity import NUMERIC_INTEGRITY_VERSION
from Backend.Core.preview_presentation import preview_presentation, validate_preview_pdf
from Backend.Core.providers import HostedLLMClient
from Backend.Core.reference_demand import profile_for
from Backend.Core.render_transaction import render_pdf_atomically


class _OutputNames:
    """Reserve the whole document set's names, including on case-folded volumes."""

    def __init__(self) -> None:
        self._roles: set[str] = set()
        self._filenames: set[str] = set()

    def add(self, role: str, filename: str) -> None:
        if not filename or filename == ".." or Path(filename).name != filename:
            raise ValueError("Artifact filenames must be direct children")
        if role in self._roles:
            raise ValueError("Family output roles must be distinct")
        key = normalize("NFD", normalize("NFD", filename).casefold())
        if key in self._filenames:
            raise ValueError("Family output filenames must be distinct")
        self._roles.add(role)
        self._filenames.add(key)


def _check_staged_files(paths: dict[str, Path], directory: Path) -> None:
    parent = directory.resolve()
    if any(
        path.is_symlink() or not path.is_file() or path.resolve().parent != parent
        for path in paths.values()
    ):
        raise ValueError("Family outputs must be files inside their staging directory")


def run_family_adapter[Syllabus, Rule, Assessment, Context](
    adapter: FamilyAdapter[Syllabus, Rule, Assessment, Context],
    *,
    paper: str,
    syllabus_path: Path,
    output_dir: Path,
    seed: int | None,
    model: str = default_ollama_model(),
    ollama_url: str = "http://localhost:11434",
    dry_run: bool = True,
    progress: ProgressCallback | None = None,
    client: JSONGenerationClient | None = None,
    checkpoint_path: Path | None = None,
) -> dict[str, Path]:
    emit = progress or (lambda _message: None)
    emit(adapter.load_message)
    syllabus = adapter.load_syllabus(syllabus_path)
    rule = adapter.load_rule(paper)
    effective_seed = adapter.resolve_seed(seed) if adapter.resolve_seed else seed
    if adapter.seed_message is not None:
        emit(adapter.seed_message(effective_seed))
    emit(adapter.build_message)
    built = adapter.build(rule, syllabus, effective_seed)
    if isinstance(built, BuildResult):
        assessment, context = built.assessment, built.context
    else:
        assessment, context = built, None

    # Preview uses the seeded blueprint and makes no authoring requests.
    question_client = client
    if dry_run:
        emit(adapter.preview_message)
    else:
        emit(f"Generating and independently reviewing questions with {model}")
        factory = adapter.client_factory or _hosted_client
        question_client = question_client or factory(model, ollama_url)
        # Resumed items must match the family blueprint, provider and review versions.
        identity_payload = (
            adapter.checkpoint_identity(assessment, rule, paper)
            if adapter.checkpoint_identity
            else assessment
        )
        checkpoint_store = (
            AssessmentCheckpointStore(
                checkpoint_path,
                identity_for_blueprint(
                    identity_payload,
                    provider=str(getattr(question_client, "provider", "ollama")),
                    model=str(getattr(question_client, "model", model)),
                    prompt_version=(
                        f"{adapter.prompt_version}:{NUMERIC_INTEGRITY_VERSION}:"
                        f"{ASSESSMENT_REVIEW_VERSION}"
                    ),
                ),
            )
            if checkpoint_path is not None
            else None
        )
        if adapter.improve is not None:
            assessment = adapter.improve(
                assessment,
                syllabus,
                rule,
                question_client,
                progress,
                checkpoint_store,
            )
            if adapter.calibrate_difficulty is None:
                raise ValueError(
                    f"{adapter.id} has a custom AI pipeline without a "
                    "reference-demand reviewer"
                )
            assessment = adapter.calibrate_difficulty(
                assessment,
                syllabus,
                rule,
                question_client,
                progress,
            )
        else:
            demand_profile = profile_for(adapter.id, paper)
            assessment = generate_unique_paper(
                assessment,
                rule=rule,
                syllabus_topics=syllabus.topics,
                syllabus_topic_ids=syllabus.topic_ids,
                client=question_client,
                subject=adapter.subject_label,
                progress=progress,
                checkpoint_store=checkpoint_store,
                policy=GenerationPolicy(
                    require_independent_solution=True,
                    require_difficulty_review=True,
                ),
                demand_profile=demand_profile,
            )

    if adapter.validate is not None:
        emit(adapter.validation_message)
        adapter.validate(assessment, rule, syllabus)

    assessment_name = f"{adapter.stem(rule, paper)}-assessment.json"
    artifacts = tuple(adapter.artifacts(assessment, context, syllabus, paper))
    names = _OutputNames()
    names.add("assessment_package", assessment_name)
    for artifact in artifacts:
        names.add(artifact.role, artifact.filename)

    output_dir.mkdir(parents=True, exist_ok=True)
    # Direct family CLIs do not have the bridge's outer output transaction.
    # Keep every role private until rendering, support and packaging all succeed.
    with TemporaryDirectory(prefix=".keldin-family-", dir=output_dir) as temporary:
        staging_dir = Path(temporary)
        paths: dict[str, Path] = {}
        # Scope includes supporting PDFs; disabled scopes override outer previews.
        with preview_presentation(dry_run):
            for artifact in artifacts:
                destination = staging_dir / artifact.filename
                emit(artifact.progress_message)

                render_pdf_atomically(
                    destination,
                    artifact.renderer,
                    role=artifact.role.replace("_", " "),
                )
                paths[artifact.role] = destination

            if adapter.supporting_artifacts is not None:
                # Support writers cannot overwrite a primary file by reusing its
                # basename. Validate the returned names before combining the sets.
                with TemporaryDirectory(prefix=".support-", dir=staging_dir) as support:
                    support_dir = Path(support)
                    supporting = dict(
                        adapter.supporting_artifacts(
                            assessment,
                            context,
                            syllabus,
                            paper,
                            support_dir,
                            emit,
                        )
                    )
                    _check_staged_files(supporting, support_dir)
                    for role, path in supporting.items():
                        names.add(role, path.name)
                    for role, path in supporting.items():
                        destination = staging_dir / path.name
                        path.replace(destination)
                        paths[role] = destination
            if dry_run:
                # Check the final tagged PDFs, including those from support hooks.
                for path in paths.values():
                    if path.suffix.casefold() == ".pdf":
                        validate_preview_pdf(path)

        if adapter.output_order:
            paths = {
                role: paths[role] for role in adapter.output_order if role in paths
            } | {
                role: path
                for role, path in paths.items()
                if role not in adapter.output_order
            }

        assessment_path = staging_dir / assessment_name
        write_assessment_package(
            assessment,
            assessment_path,
            subject=adapter.backend_subject,
            paper_number=paper,
            preview=dry_run,
            provider=(
                getattr(question_client, "provider", "ollama") if not dry_run else None
            ),
            model=getattr(question_client, "model", model) if not dry_run else None,
        )
        paths["assessment_package"] = assessment_path
        _check_staged_files(paths, staging_dir)
        # The bridge may still need to validate and publish these files itself.
        paths = publish_document_set(paths, output_dir, final_publication=False)
    emit("Done")
    return paths


def _hosted_client(model: str, ollama_url: str) -> JSONGenerationClient:
    return HostedLLMClient(
        provider="ollama",
        model=model,
        api_key="",
        base_url=ollama_url,
    )

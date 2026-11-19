// Deliver generation and download results as user notifications.

import Foundation
import UserNotifications

/// Wraps `UNUserNotificationCenter` so the coordinator does not own the
/// authorization state machine or build notification content itself.
@MainActor
final class WorkNotificationCenter {
    private let center: UNUserNotificationCenter

    init(center: UNUserNotificationCenter = .current()) {
        self.center = center
        center.delegate = NotificationPresenter.shared
    }

    func requestAuthorization() {
        Task {
            _ = try? await center.requestAuthorization(options: [.alert, .sound])
        }
    }

    func post(_ event: WorkNotification, language: String, enabled: Bool) {
        let copy = event.content(language: language)
        post(title: copy.title, body: copy.body, enabled: enabled)
    }

    private func post(title: String, body: String, enabled: Bool) {
        guard enabled else { return }
        Task {
            let settings = await center.notificationSettings()
            let allowed: Bool
            switch settings.authorizationStatus {
            case .authorized, .provisional, .ephemeral:
                allowed = true
            case .notDetermined:
                allowed = (try? await center.requestAuthorization(
                    options: [.alert, .sound]
                )) ?? false
            default:
                allowed = false
            }
            guard allowed else { return }

            let content = UNMutableNotificationContent()
            content.title = title
            content.body = body
            content.sound = .default
            let request = UNNotificationRequest(
                identifier: UUID().uuidString,
                content: content,
                trigger: nil
            )
            try? await center.add(request)
        }
    }
}

/// Presents notifications while the app is frontmost.
@MainActor
final class NotificationPresenter: NSObject, UNUserNotificationCenterDelegate {
    static let shared = NotificationPresenter()

    private override init() {
        super.init()
    }

    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification
    ) async -> UNNotificationPresentationOptions {
        [.banner, .sound]
    }
}

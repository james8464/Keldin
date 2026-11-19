// Share native control styling across the app.

import SwiftUI

extension View {
    func nativePrimaryActionStyle() -> some View {
        buttonStyle(.borderedProminent)
            .tint(Color("ControlAccent"))
    }

}

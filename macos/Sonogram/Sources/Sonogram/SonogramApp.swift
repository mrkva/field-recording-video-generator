import SwiftUI

@main
struct SonogramApp: App {
    @State private var appState = AppState()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(appState)
                .frame(minWidth: 900, minHeight: 700)
        }
        .windowStyle(.titleBar)
        .defaultSize(width: 1100, height: 800)
        .commands {
            CommandGroup(replacing: .newItem) {}
        }
    }
}

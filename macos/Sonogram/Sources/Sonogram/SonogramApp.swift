import SwiftUI

@main
struct SonogramApp: App {
    @StateObject private var appState = AppState()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(appState)
                .frame(minWidth: 900, minHeight: 700)
        }
        .windowStyle(.titleBar)
        .defaultSize(width: 1100, height: 800)
        .commands {
            CommandGroup(replacing: .newItem) {}
        }
    }
}

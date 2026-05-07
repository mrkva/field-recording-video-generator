import SwiftUI
import UniformTypeIdentifiers

struct DropZoneView: View {
    @Environment(AppState.self) var state
    @State private var isTargeted = false

    var body: some View {
        VStack(spacing: 20) {
            Spacer()

            Image(systemName: "waveform.badge.plus")
                .font(.system(size: 64))
                .foregroundStyle(isTargeted ? .blue : .secondary)

            Text("Drop a WAV file here")
                .font(.title2)
                .fontWeight(.medium)

            Text("or click to browse")
                .font(.subheadline)
                .foregroundStyle(.secondary)

            Button("Open File...") {
                openFilePicker()
            }
            .buttonStyle(.bordered)
            .keyboardShortcut("o", modifiers: .command)

            if let error = state.errorMessage {
                VStack(spacing: 4) {
                    Label("Error", systemImage: "exclamationmark.triangle")
                        .font(.callout)
                        .fontWeight(.medium)
                        .foregroundStyle(.red)
                    Text(error)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                        .frame(maxWidth: 400)
                }
                .padding(12)
                .background(.red.opacity(0.06))
                .clipShape(RoundedRectangle(cornerRadius: 8))
            }

            Spacer()

            VStack(spacing: 4) {
                Text("sonogram")
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundStyle(.tertiary)
                Text("Field recording → scrolling spectrogram video")
                    .font(.caption2)
                    .foregroundStyle(.quaternary)
            }
            .padding(.bottom, 20)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(
            RoundedRectangle(cornerRadius: 12)
                .strokeBorder(
                    isTargeted ? Color.blue : Color.secondary.opacity(0.3),
                    style: StrokeStyle(lineWidth: 2, dash: [8, 4])
                )
                .padding(20)
        )
        .onDrop(of: [.fileURL], isTargeted: $isTargeted) { providers in
            handleDrop(providers)
        }
    }

    private func openFilePicker() {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [.wav, .audio]
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        panel.message = "Select a WAV audio file"
        if panel.runModal() == .OK, let url = panel.url {
            Task { await state.loadAudioFile(url: url) }
        }
    }

    private func handleDrop(_ providers: [NSItemProvider]) -> Bool {
        guard let provider = providers.first else { return false }
        provider.loadItem(forTypeIdentifier: UTType.fileURL.identifier, options: nil) { item, _ in
            guard let data = item as? Data,
                  let url = URL(dataRepresentation: data, relativeTo: nil),
                  url.pathExtension.lowercased() == "wav" else { return }
            Task { @MainActor in
                await state.loadAudioFile(url: url)
            }
        }
        return true
    }
}

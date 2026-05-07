import SwiftUI
import UniformTypeIdentifiers

struct ContentView: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        NavigationSplitView {
            sidebar
                .navigationSplitViewColumnWidth(min: 220, ideal: 260, max: 320)
        } detail: {
            if state.isGenerating || state.phase == .done {
                GenerationView()
            } else if state.audioFile != nil {
                ScrollView {
                    VStack(spacing: 0) {
                        audioInfoBanner
                        Divider()
                        HStack(alignment: .top, spacing: 0) {
                            VStack(spacing: 20) {
                                MetadataFormView()
                                SpectrogramSettingsView()
                            }
                            .frame(maxWidth: .infinity)
                            .padding(20)

                            Divider()

                            VStack(spacing: 20) {
                                FormatPickerView()
                                PresetGridView()
                                outputSettings
                            }
                            .frame(maxWidth: .infinity)
                            .padding(20)
                        }
                        Divider()
                        generateBar
                    }
                }
            } else {
                DropZoneView()
            }
        }
        .onDrop(of: [.fileURL], isTargeted: nil) { providers in
            handleDrop(providers)
        }
        .sheet(isPresented: $state.showCoordinatePicker) {
            CoordinatePickerView(coordinates: $state.coordinates)
        }
    }

    private var sidebar: some View {
        List {
            Section("Audio File") {
                if let file = state.audioFile {
                    Label(file.filename, systemImage: "waveform")
                        .lineLimit(1)
                        .truncationMode(.middle)
                    Text("\(file.sampleRateLabel) · \(file.channelLabel) · \(file.bitDepthLabel)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Text(file.durationFormatted)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                } else {
                    Text("No file loaded")
                        .foregroundStyle(.tertiary)
                }
            }

            Section("Saved Presets") {
                if state.presetStore.presets.isEmpty {
                    Text("No presets")
                        .font(.caption)
                        .foregroundStyle(.tertiary)
                } else {
                    ForEach(state.presetStore.presets) { preset in
                        Button {
                            withAnimation { state.loadPreset(preset) }
                        } label: {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(preset.name)
                                    .font(.callout)
                                HStack(spacing: 4) {
                                    Text(preset.formatID)
                                    Text("·")
                                    Text(preset.specMethod)
                                    Text("·")
                                    Text(preset.playbackSpeed)
                                }
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                            }
                        }
                        .buttonStyle(.plain)
                    }
                }
            }

            Section("Method") {
                Picker("Spectrogram", selection: $state.specMethod) {
                    Text("Standard").tag("standard")
                    Text("Reassigned").tag("reassigned")
                }
                .pickerStyle(.segmented)
                .onChange(of: state.specMethod) { _, _ in
                    state.fftWindow = state.defaultFFT
                }
            }

            if state.isGenerating || state.phase == .done {
                Section("Status") {
                    Label(state.phase.rawValue, systemImage: state.phase == .done ? "checkmark.circle" : "gear")
                }
            }
        }
        .listStyle(.sidebar)
    }

    private var audioInfoBanner: some View {
        HStack(spacing: 16) {
            if let file = state.audioFile {
                Image(systemName: "waveform")
                    .font(.title2)
                    .foregroundStyle(.secondary)
                VStack(alignment: .leading, spacing: 2) {
                    Text(file.filename)
                        .font(.headline)
                    Text("\(file.sampleRateLabel) · \(file.channelLabel) · \(file.bitDepthLabel) · \(file.durationFormatted)")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                if file.hasBWF {
                    Label("BWF", systemImage: "info.circle")
                        .font(.caption)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(.blue.opacity(0.1))
                        .clipShape(Capsule())
                }
                nyquistBadge(file.nyquist)
                Button("Change File") {
                    openFilePicker()
                }
                .buttonStyle(.bordered)
            }
        }
        .padding(12)
        .background(.bar)
    }

    private func nyquistBadge(_ nyquist: Int) -> some View {
        VStack(spacing: 1) {
            Text("Nyquist")
                .font(.caption2)
                .foregroundStyle(.tertiary)
            Text("\(nyquist / 1000) kHz")
                .font(.caption)
                .fontWeight(.medium)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(.ultraThinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 6))
    }

    private var outputSettings: some View {
        GroupBox("Output") {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Text("Speed")
                        .frame(width: 80, alignment: .trailing)
                    TextField("1x", text: $state.playbackSpeed)
                        .textFieldStyle(.roundedBorder)
                        .frame(width: 60)
                    if let dur = state.estimatedDuration {
                        Text("→ \(state.estimatedDurationFormatted)")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        if state.parseSpeed(state.playbackSpeed) != 1.0 {
                            Text("(\(String(format: "%.1f", dur))s)")
                                .font(.caption2)
                                .foregroundStyle(.tertiary)
                        }
                    }
                }

                HStack {
                    Text("Output")
                        .frame(width: 80, alignment: .trailing)
                    TextField("output.mp4", text: $state.outputPath)
                        .textFieldStyle(.roundedBorder)
                        .lineLimit(1)
                        .truncationMode(.middle)
                    Button("...") {
                        pickOutputPath()
                    }
                }

                HStack {
                    Text("")
                        .frame(width: 80)
                    Toggle("Normalize audio (-16 LUFS)", isOn: $state.normalizeAudio)
                    Spacer()
                }

                HStack {
                    Text("")
                        .frame(width: 80)
                    Toggle("Show timecode", isOn: $state.showTimecode)
                    Spacer()
                }

                HStack {
                    Text("")
                        .frame(width: 80)
                    Toggle("Open after export", isOn: $state.openAfterExport)
                    Spacer()
                }

                HStack {
                    Text("Photo")
                        .frame(width: 80, alignment: .trailing)
                    TextField("Optional photo path", text: $state.photoPath)
                        .textFieldStyle(.roundedBorder)
                    Button("...") {
                        pickPhoto()
                    }
                }
            }
            .padding(4)
        }
    }

    private var generateBar: some View {
        HStack {
            Spacer()
            Button(action: {
                state.autocomplete.addEntry(
                    subject: state.subject,
                    location: state.location,
                    recorder: state.recorder,
                    coords: state.coordinates
                )
                Task { await state.generate() }
            }) {
                Label("Generate Video", systemImage: "film")
                    .font(.headline)
                    .padding(.horizontal, 24)
                    .padding(.vertical, 8)
            }
            .buttonStyle(.borderedProminent)
            .disabled(state.audioFile == nil)
            .keyboardShortcut(.return, modifiers: .command)
            Spacer()
        }
        .padding(16)
        .background(.bar)
    }

    private func handleDrop(_ providers: [NSItemProvider]) -> Bool {
        guard let provider = providers.first else { return false }
        provider.loadItem(forTypeIdentifier: "public.file-url", options: nil) { item, _ in
            guard let data = item as? Data,
                  let url = URL(dataRepresentation: data, relativeTo: nil),
                  url.pathExtension.lowercased() == "wav" else { return }
            Task { @MainActor in
                await state.loadAudioFile(url: url)
            }
        }
        return true
    }

    private func openFilePicker() {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [.wav, .audio]
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        if panel.runModal() == .OK, let url = panel.url {
            Task { await state.loadAudioFile(url: url) }
        }
    }

    private func pickOutputPath() {
        let panel = NSSavePanel()
        panel.allowedContentTypes = [.mpeg4Movie]
        panel.nameFieldStringValue = URL(fileURLWithPath: state.outputPath).lastPathComponent
        if panel.runModal() == .OK, let url = panel.url {
            state.outputPath = url.path
        }
    }

    private func pickPhoto() {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [.image]
        panel.allowsMultipleSelection = false
        if panel.runModal() == .OK, let url = panel.url {
            state.photoPath = url.path
        }
    }
}

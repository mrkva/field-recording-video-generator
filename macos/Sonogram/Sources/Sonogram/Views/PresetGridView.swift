import SwiftUI

struct PresetGridView: View {
    @Environment(AppState.self) var state
    @State private var presetName: String = ""

    var body: some View {
        @Bindable var state = state
        GroupBox("Presets") {
            VStack(alignment: .leading, spacing: 10) {
                if state.presetStore.presets.isEmpty {
                    Text("No saved presets yet. Configure your settings and save them for quick reuse.")
                        .font(.caption)
                        .foregroundStyle(.tertiary)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 8)
                } else {
                    ForEach(state.presetStore.presets) { preset in
                        PresetRow(preset: preset) {
                            withAnimation { state.loadPreset(preset) }
                        } onDelete: {
                            withAnimation { state.presetStore.delete(preset: preset) }
                        }
                    }
                }

                Divider()

                HStack {
                    Button {
                        state.showSavePreset = true
                    } label: {
                        Label("Save Current Settings", systemImage: "plus.circle")
                            .font(.callout)
                    }
                    .buttonStyle(.borderless)
                }
            }
            .padding(4)
        }
        .sheet(isPresented: $state.showSavePreset) {
            SavePresetSheet()
        }
    }
}

struct PresetRow: View {
    let preset: UserPreset
    let onLoad: () -> Void
    let onDelete: () -> Void

    var body: some View {
        HStack(spacing: 8) {
            VStack(alignment: .leading, spacing: 2) {
                Text(preset.name)
                    .font(.callout)
                    .fontWeight(.medium)
                HStack(spacing: 6) {
                    Text(preset.formatID)
                    Text("·")
                    Text(preset.specMethod)
                    Text("·")
                    Text("FFT \(preset.fftWindow)")
                    Text("·")
                    Text(preset.playbackSpeed)
                }
                .font(.caption2)
                .foregroundStyle(.secondary)
                if !preset.subject.isEmpty || !preset.location.isEmpty {
                    HStack(spacing: 6) {
                        if !preset.subject.isEmpty {
                            Text(preset.subject)
                        }
                        if !preset.location.isEmpty {
                            Text("@ \(preset.location)")
                        }
                    }
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
                    .lineLimit(1)
                }
            }

            Spacer()

            Button("Load") { onLoad() }
                .buttonStyle(.bordered)
                .controlSize(.small)

            Button(role: .destructive) { onDelete() } label: {
                Image(systemName: "trash")
                    .font(.caption)
            }
            .buttonStyle(.borderless)
        }
        .padding(.vertical, 4)
    }
}

struct SavePresetSheet: View {
    @Environment(AppState.self) var state
    @State private var name: String = ""
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(spacing: 16) {
            Text("Save Preset")
                .font(.headline)

            TextField("Preset name", text: $name)
                .textFieldStyle(.roundedBorder)
                .frame(width: 300)

            VStack(alignment: .leading, spacing: 4) {
                Text("Saves all current settings:")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                HStack(spacing: 12) {
                    settingPill("Format", state.selectedFormat.name)
                    settingPill("Method", state.specMethod)
                    settingPill("FFT", "\(state.fftWindow)")
                    settingPill("Speed", state.playbackSpeed)
                }
                HStack(spacing: 12) {
                    settingPill("Range", "\(state.freqMin)-\(state.freqMax) Hz")
                    settingPill("Dyn", "\(state.dynamicRange) dB")
                    settingPill("PPS", "\(state.specPPS)")
                }
                if !state.subject.isEmpty {
                    settingPill("Subject", state.subject)
                }
                if !state.location.isEmpty {
                    settingPill("Location", state.location)
                }
            }

            HStack {
                Button("Cancel") { dismiss() }
                    .keyboardShortcut(.cancelAction)
                Button("Save") {
                    let preset = UserPreset(name: name, from: state)
                    state.presetStore.save(preset: preset)
                    dismiss()
                }
                .buttonStyle(.borderedProminent)
                .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty)
                .keyboardShortcut(.defaultAction)
            }
        }
        .padding(24)
        .frame(minWidth: 400)
    }

    private func settingPill(_ label: String, _ value: String) -> some View {
        HStack(spacing: 3) {
            Text(label)
                .foregroundStyle(.tertiary)
            Text(value)
        }
        .font(.caption2)
        .padding(.horizontal, 6)
        .padding(.vertical, 2)
        .background(.quaternary.opacity(0.3))
        .clipShape(Capsule())
    }
}

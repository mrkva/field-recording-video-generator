import SwiftUI

struct SpectrogramSettingsView: View {
    @Environment(AppState.self) var state

    private let fftOptions = [256, 512, 1024, 2048, 4096, 8192]

    var body: some View {
        @Bindable var state = state
        GroupBox("Spectrogram") {
            VStack(alignment: .leading, spacing: 12) {
                // Method picker
                HStack {
                    Text("Method")
                        .frame(width: 80, alignment: .trailing)
                        .foregroundStyle(.secondary)
                    Picker("", selection: $state.specMethod) {
                        Text("Standard").tag("standard")
                        Text("Reassigned").tag("reassigned")
                    }
                    .pickerStyle(.segmented)
                    .frame(maxWidth: 200)
                    .onChange(of: state.specMethod) { _, _ in
                        state.fftWindow = state.defaultFFT
                    }
                }

                // FFT window
                HStack {
                    Text("FFT Window")
                        .frame(width: 80, alignment: .trailing)
                        .foregroundStyle(.secondary)
                    Picker("", selection: $state.fftWindow) {
                        ForEach(fftOptions, id: \.self) { size in
                            Text("\(size)").tag(size)
                        }
                    }
                    .frame(width: 100)
                    fftBadge
                }

                Text(state.fftHint)
                    .font(.caption)
                    .foregroundStyle(.tertiary)
                    .padding(.leading, 84)

                // Frequency range
                HStack {
                    Text("Freq Range")
                        .frame(width: 80, alignment: .trailing)
                        .foregroundStyle(.secondary)
                    HStack(spacing: 4) {
                        // .grouping(.never) keeps "96000" round-tripping as
                        // plain digits — with locale grouping enabled,
                        // "96 000" parsed back as just "96" because the
                        // thin-space separator broke the input.
                        TextField("20", value: $state.freqMin, format: .number.grouping(.never))
                            .textFieldStyle(.roundedBorder)
                            .frame(width: 70)
                        Text("–")
                        TextField("22050", value: $state.freqMax, format: .number.grouping(.never))
                            .textFieldStyle(.roundedBorder)
                            .frame(width: 70)
                        Text("Hz")
                            .foregroundStyle(.secondary)
                    }
                    if let file = state.audioFile {
                        // String() avoids SwiftUI's LocalizedStringKey
                        // auto-grouping (which prints "96 000" in cs/fr) so
                        // the hint matches what the no-grouping field accepts.
                        Text("(Nyquist: \(String(file.nyquist)) Hz)")
                            .font(.caption)
                            .foregroundStyle(.tertiary)
                    }
                }

                // Dynamic range
                HStack {
                    Text("Dyn Range")
                        .frame(width: 80, alignment: .trailing)
                        .foregroundStyle(.secondary)
                    Slider(value: Binding(
                        get: { Double(state.dynamicRange) },
                        set: { state.dynamicRange = Int($0) }
                    ), in: 20...120, step: 5) {
                        Text("")
                    }
                    .frame(maxWidth: 180)
                    Text("\(state.dynamicRange) dB")
                        .font(.caption)
                        .monospacedDigit()
                        .frame(width: 50)
                }

                // Color scheme
                HStack {
                    Text("Colors")
                        .frame(width: 80, alignment: .trailing)
                        .foregroundStyle(.secondary)
                    Picker("", selection: $state.colormap) {
                        Text("Inferno").tag("inferno")
                        Text("Paper (B/W)").tag("gray_r")
                        Text("Viridis").tag("viridis")
                        Text("Magma").tag("magma")
                        Text("Hot").tag("hot")
                        Text("Bone").tag("bone")
                    }
                    .frame(maxWidth: 160)
                }

                // Pixels per second (scroll speed)
                HStack {
                    Text("Speed")
                        .frame(width: 80, alignment: .trailing)
                        .foregroundStyle(.secondary)
                    Slider(value: Binding(
                        get: { Double(state.specPPS) },
                        set: { state.specPPS = Int($0) }
                    ), in: 50...500, step: 25) {
                        Text("")
                    }
                    .frame(maxWidth: 180)
                    Text("\(state.specPPS) px/s")
                        .font(.caption)
                        .monospacedDigit()
                        .frame(width: 60)
                }
            }
            .padding(4)
        }
    }

    @ViewBuilder
    private var fftBadge: some View {
        let timeRes = 1000.0 * Double(state.fftWindow) / Double(state.audioFile?.sampleRate ?? 44100)
        let freqRes = Double(state.audioFile?.sampleRate ?? 44100) / Double(state.fftWindow)
        VStack(alignment: .leading, spacing: 1) {
            Text(String(format: "%.1f ms", timeRes))
                .font(.caption2)
                .foregroundStyle(.orange)
            Text(String(format: "%.1f Hz", freqRes))
                .font(.caption2)
                .foregroundStyle(.cyan)
        }
        .padding(.horizontal, 6)
        .padding(.vertical, 2)
        .background(.ultraThinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 4))
    }
}

import SwiftUI
import AVKit

struct GenerationView: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        VStack(spacing: 0) {
            if state.phase == .done, let videoPath = state.generatedVideoPath {
                videoPreview(path: videoPath)
            } else {
                progressView
            }

            Divider()
            logView
        }
    }

    private var progressView: some View {
        VStack(spacing: 20) {
            Spacer()

            ProgressView()
                .scaleEffect(1.5)
                .padding()

            Text(state.phase.rawValue)
                .font(.title3)
                .fontWeight(.medium)

            pipelineSteps

            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding()
    }

    private var pipelineSteps: some View {
        HStack(spacing: 16) {
            stepIndicator("Probe", phase: .probing)
            stepArrow
            stepIndicator("Spectrogram", phase: .spectrogram)
            stepArrow
            stepIndicator("Info", phase: .infoPanel)
            stepArrow
            stepIndicator("Scale", phase: .freqScale)
            stepArrow
            stepIndicator("Map", phase: .mapAnimation)
            stepArrow
            stepIndicator("Encode", phase: .compositing)
        }
        .padding()
    }

    private func stepIndicator(_ label: String, phase: GenerationPhase) -> some View {
        let isCurrent = state.phase == phase
        let isPast = phaseOrder(state.phase) > phaseOrder(phase)
        let isDone = state.phase == .done

        return VStack(spacing: 4) {
            Circle()
                .fill(isDone || isPast ? Color.green : isCurrent ? Color.blue : Color.secondary.opacity(0.3))
                .frame(width: 10, height: 10)
                .overlay {
                    if isCurrent && !isDone {
                        Circle()
                            .stroke(Color.blue.opacity(0.4), lineWidth: 2)
                            .frame(width: 16, height: 16)
                    }
                }
            Text(label)
                .font(.caption2)
                .foregroundStyle(isCurrent ? .primary : .secondary)
        }
    }

    private var stepArrow: some View {
        Image(systemName: "chevron.right")
            .font(.caption2)
            .foregroundStyle(.tertiary)
    }

    private func phaseOrder(_ phase: GenerationPhase) -> Int {
        switch phase {
        case .idle: return 0
        case .probing: return 1
        case .spectrogram: return 2
        case .infoPanel: return 3
        case .freqScale: return 4
        case .mapAnimation: return 5
        case .compositing: return 6
        case .done: return 7
        case .failed: return -1
        }
    }

    private func videoPreview(path: String) -> some View {
        VStack(spacing: 12) {
            let url = URL(fileURLWithPath: path)
            if FileManager.default.fileExists(atPath: path) {
                VideoPlayer(player: AVPlayer(url: url))
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                    .padding()
            } else {
                VStack {
                    Image(systemName: "checkmark.circle")
                        .font(.system(size: 48))
                        .foregroundStyle(.green)
                    Text("Video generated")
                        .font(.title3)
                    Text(path)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                        .truncationMode(.middle)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }

            HStack(spacing: 12) {
                Button("Show in Finder") {
                    NSWorkspace.shared.selectFile(path, inFileViewerRootedAtPath: "")
                }
                .buttonStyle(.bordered)

                Button("Open") {
                    NSWorkspace.shared.open(url)
                }
                .buttonStyle(.bordered)

                Spacer()

                Button("New Video") {
                    state.phase = .idle
                    state.generatedVideoPath = nil
                    state.progressLog = []
                }
                .buttonStyle(.borderedProminent)
            }
            .padding(.horizontal)
            .padding(.bottom, 8)
        }
    }

    private var logView: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text("Log")
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundStyle(.secondary)
                Spacer()
                Text("\(state.progressLog.count) lines")
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)

            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 1) {
                        ForEach(Array(state.progressLog.enumerated()), id: \.offset) { index, line in
                            Text(line)
                                .font(.system(.caption2, design: .monospaced))
                                .foregroundStyle(line.contains("ERROR") ? .red : .secondary)
                                .id(index)
                                .textSelection(.enabled)
                        }
                    }
                    .padding(.horizontal, 12)
                    .padding(.vertical, 4)
                }
                .frame(height: 120)
                .background(.black.opacity(0.03))
                .onChange(of: state.progressLog.count) { _, _ in
                    if let last = state.progressLog.indices.last {
                        proxy.scrollTo(last, anchor: .bottom)
                    }
                }
            }
        }
    }
}

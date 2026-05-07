import SwiftUI

struct GenerationView: View {
    @Environment(AppState.self) var state

    var body: some View {
        VStack(spacing: 0) {
            if state.phase == .done, let videoPath = state.generatedVideoPath {
                completionView(path: videoPath)
            } else if state.phase == .failed {
                failedView
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

    private var failedView: some View {
        VStack(spacing: 16) {
            Spacer()
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 48))
                .foregroundStyle(.red)
            Text("Generation failed")
                .font(.title3)
            Button("Back to Settings") {
                state.phase = .idle
                state.generatedVideoPath = nil
            }
            .buttonStyle(.borderedProminent)
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
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

    private func completionView(path: String) -> some View {
        VStack(spacing: 16) {
            Spacer()

            Image(systemName: "checkmark.circle")
                .font(.system(size: 56))
                .foregroundStyle(.green)

            Text("Video generated")
                .font(.title2)
                .fontWeight(.medium)

            Text(URL(fileURLWithPath: path).lastPathComponent)
                .font(.callout)
                .foregroundStyle(.secondary)

            Text(path)
                .font(.caption2)
                .foregroundStyle(.tertiary)
                .lineLimit(1)
                .truncationMode(.middle)
                .frame(maxWidth: 500)

            Spacer()

            HStack(spacing: 12) {
                Button("Show in Finder") {
                    NSWorkspace.shared.selectFile(path, inFileViewerRootedAtPath: "")
                }
                .buttonStyle(.bordered)

                Button("Open in Player") {
                    NSWorkspace.shared.open(URL(fileURLWithPath: path))
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
            .padding(.horizontal, 20)
            .padding(.bottom, 12)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .task {
            if state.openAfterExport {
                NSWorkspace.shared.open(URL(fileURLWithPath: path))
            }
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

            ScrollView {
                LazyVStack(alignment: .leading, spacing: 1) {
                    ForEach(state.progressLog.indices, id: \.self) { index in
                        Text(state.progressLog[index])
                            .font(.system(.caption2, design: .monospaced))
                            .foregroundStyle(state.progressLog[index].contains("ERROR") ? .red : .secondary)
                            .textSelection(.enabled)
                    }
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 4)
            }
            .frame(height: 120)
            .background(.black.opacity(0.03))
            .defaultScrollAnchor(.bottom)
        }
    }
}

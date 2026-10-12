import SwiftUI

struct ThreadView: View {
    @StateObject var viewModel: ThreadViewModel
    @State private var draft = ""

    var body: some View {
        VStack {
            List(viewModel.messages) { message in
                Text(message.text)
                    .contextMenu { Button("Report") { viewModel.report(message) } }
            }
            if viewModel.peerIsTyping { Text("typing...") }
            HStack {
                TextField("Message", text: $draft)
                    .onChange(of: draft) { _ in viewModel.typing() }
                Button("Send") { Task { await viewModel.send(draft); draft = "" } }
                    .disabled(draft.isEmpty || viewModel.isSending)
            }
            if let error = viewModel.sendError { Text(error).foregroundStyle(.red) }
        }
        .task { await viewModel.open() }
        .onDisappear { viewModel.close() }
    }
}

# Code map

Canonical contributor rules: `AGENTS.md`.

| Topic | Location |
|---|---|
| Existing macOS application | `WhisperShortcut/` |
| macOS orchestration/state | `WhisperShortcut/MenuBarController.swift`, `WhisperShortcut/AppState.swift`, `WhisperShortcut/SpeechService.swift` |
| macOS providers | `WhisperShortcut/LLMChatProvider.swift`, provider-named Swift files |
| macOS audio | `WhisperShortcut/AudioRecorder.swift`, `LiveMeetingRecorder.swift`, `SystemAudioCapture.swift` |
| macOS tests and project | `WhisperShortcutTests/`, `WhisperShortcut.xcodeproj/` |
| Ubuntu desktop prototype | `apps/linux/prototype/` |
| Linux commands/checks | `scripts/linux/`, `docs/development/platform-commands.md` |
| Approved migration | `plans/active/ubuntu-multiplatform-design.md`, `ubuntu-foundation-plan.md` |
| Tooling dependencies | `docs/development/fork-tooling-inventory.md` |

Mac source/project relocation is deferred until Mac verification is available.
Original maintainer automation under scripts/plans is historical, not an active
queue. No permanent OS branches are used.

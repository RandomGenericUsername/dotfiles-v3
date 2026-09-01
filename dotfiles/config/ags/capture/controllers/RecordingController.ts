import { CaptureController } from "./CaptureController"

export class RecordingController extends CaptureController {
  async start() {
    this.state = "starting"
    // Launch GPU Screen Recorder / wf-recorder here.
    this.state = "recording"
  }

  async stop() {
    this.state = "stopping"
    // Stop recorder process and finalize file.
    this.state = "idle"
  }

  async pause() {
    this.state = "paused"
    // Send pause signal to the backend process.
  }

  async resume() {
    this.state = "recording"
    // Send resume signal to the backend process.
  }
}

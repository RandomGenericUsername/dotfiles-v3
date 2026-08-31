import { CaptureController } from "./CaptureController"

export class ScreenshotController extends CaptureController {
  async capture() {
    this.state = "starting"
    // Launch grim + slurp + wl-copy and finalize output.
    this.state = "idle"
  }
}

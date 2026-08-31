export type CaptureState = "idle" | "starting" | "recording" | "paused" | "stopping" | "error"

export abstract class CaptureController {
  protected state: CaptureState = "idle"

  getState(): CaptureState {
    return this.state
  }
}

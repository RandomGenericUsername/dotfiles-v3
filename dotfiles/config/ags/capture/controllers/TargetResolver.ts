export type ResolvedGeometry = {
  x: number
  y: number
  width: number
  height: number
}

export class TargetResolver {
  resolveRegion(): ResolvedGeometry {
    return { x: 0, y: 0, width: 0, height: 0 }
  }

  resolveScreen(): ResolvedGeometry {
    return { x: 0, y: 0, width: 0, height: 0 }
  }

  resolveWindow(): ResolvedGeometry {
    return { x: 0, y: 0, width: 0, height: 0 }
  }
}

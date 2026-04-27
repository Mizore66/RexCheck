import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static targets = []

  connect() {
    // Auto-refresh every 30 seconds via Turbo Frame
    this.refreshInterval = setInterval(() => {
      this.refresh()
    }, 30000)
  }

  disconnect() {
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval)
    }
  }

  refresh() {
    const frame = document.querySelector("turbo-frame#pool_grid")
    if (frame) {
      frame.src = window.location.href
      frame.reload()
    }
  }
}

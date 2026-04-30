import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static targets = ["tab", "panel"]

  connect() {
    console.log("Dashboard connected. ActionCable initialized.")
  }

  showTab(event) {
    const selectedTab = event.params.tab

    this.panelTargets.forEach((panel) => {
      panel.classList.toggle("hidden", panel.dataset.dashboardPanelId !== selectedTab)
    })

    this.tabTargets.forEach((tab) => {
      const isActive = tab.dataset.dashboardTabParam === selectedTab
      tab.classList.toggle("border-emerald-800/60", isActive)
      tab.classList.toggle("bg-emerald-900/20", isActive)
      tab.classList.toggle("text-emerald-300", isActive)
      tab.classList.toggle("border-slate-800", !isActive)
      tab.classList.toggle("bg-slate-900/60", !isActive)
      tab.classList.toggle("text-slate-400", !isActive)
    })
  }

  disconnect() {}
}

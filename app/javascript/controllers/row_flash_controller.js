import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  connect() {
    this.element.classList.add("animate-row-flash")
    this.element.addEventListener("animationend", () => {
      this.element.classList.remove("animate-row-flash")
    }, { once: true })
  }
}

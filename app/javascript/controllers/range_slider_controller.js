import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static targets = ["liquiditySlider", "liquidityValue", "volumeSlider", "volumeValue", "ageSlider", "ageValue"]

  connect() {
    console.log("Range slider controller connected")
  }

  updateLiquidity() {
    this.liquidityValueTarget.textContent = this.liquiditySliderTarget.value
  }

  updateVolume() {
    this.volumeValueTarget.textContent = this.volumeSliderTarget.value
  }

  updateAge() {
    this.ageValueTarget.textContent = this.ageSliderTarget.value
  }
}

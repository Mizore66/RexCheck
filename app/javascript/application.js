import "@hotwired/turbo-rails"
import { Application } from "@hotwired/stimulus"
import DashboardController from "./controllers/dashboard_controller"
import RangeSliderController from "./controllers/range_slider_controller"
import RowFlashController from "./controllers/row_flash_controller"
import SidebarController from "./controllers/sidebar_controller"

const application = Application.start()
application.register("dashboard", DashboardController)
application.register("range-slider", RangeSliderController)
application.register("row-flash", RowFlashController)
application.register("sidebar", SidebarController)

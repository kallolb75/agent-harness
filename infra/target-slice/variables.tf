variable "project_id" {
  description = "The client's Google Cloud project."
  type        = string
}

variable "region" {
  description = "One region for the first slice."
  type        = string
  default     = "us-central1"
}

variable "pricing_image" {
  description = "Image for the pricing service, built from the translated ORDPRICE rules."
  type        = string
}

variable "orders_image" {
  description = "Image for the orders service."
  type        = string
}

output "pricing_url" {
  value = google_cloud_run_v2_service.pricing.uri
}

output "orders_url" {
  value = google_cloud_run_v2_service.orders.uri
}

output "order_events_topic" {
  value = google_pubsub_topic.order_events.id
}

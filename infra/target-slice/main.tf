# Target state, first strangler slice: pricing and order capture on Google Cloud.
# A sketch for the interview: terraform validate only, never applied.
#
#   orders (Cloud Run)  --sync, IAM-authenticated-->  pricing (Cloud Run, internal only)
#   orders              --writes-->                   Cloud SQL for PostgreSQL (orders schema)
#   orders              --publishes OrderPlaced-->    Pub/Sub order-events
#   billing             <--pull subscription--        order-events (dead letters after 5 tries)

locals {
  apis = [
    "run.googleapis.com",
    "pubsub.googleapis.com",
    "sqladmin.googleapis.com",
    "artifactregistry.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.apis)
  service            = each.value
  disable_on_destroy = false
}

data "google_project" "this" {}

# One identity per service, each with only the grants below.
resource "google_service_account" "pricing" {
  account_id   = "pricing-svc"
  display_name = "Pricing service"
}

resource "google_service_account" "orders" {
  account_id   = "orders-svc"
  display_name = "Orders service"
}

resource "google_service_account" "billing" {
  account_id   = "billing-worker"
  display_name = "Billing worker"
}

# Pricing: stateless, internal only. The rules come from ORDPRICE, proven by parity tests.
resource "google_cloud_run_v2_service" "pricing" {
  name                = "pricing"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_INTERNAL_ONLY"
  deletion_protection = false

  template {
    service_account = google_service_account.pricing.email
    scaling {
      min_instance_count = 1 # no cold start on the order path
      max_instance_count = 20
    }
    containers {
      image = var.pricing_image
      resources {
        limits = { cpu = "1", memory = "512Mi" }
      }
    }
  }
  depends_on = [google_project_service.apis]
}

# Only the orders service may call pricing. No allUsers invoker anywhere.
resource "google_cloud_run_v2_service_iam_member" "orders_calls_pricing" {
  name     = google_cloud_run_v2_service.pricing.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.orders.email}"
}

# Orders data: PostgreSQL, IAM database login, no passwords.
resource "google_sql_database_instance" "orders" {
  name                = "orders-db"
  database_version    = "POSTGRES_16"
  region              = var.region
  deletion_protection = true

  settings {
    tier              = "db-custom-2-7680"
    availability_type = "REGIONAL" # a standby in a second zone
    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
    }
    database_flags {
      name  = "cloudsql.iam_authentication"
      value = "on"
    }
    ip_configuration {
      ipv4_enabled = true # reached only through the Cloud SQL connector; no authorized networks
      ssl_mode     = "ENCRYPTED_ONLY"
    }
  }
  depends_on = [google_project_service.apis]
}

resource "google_sql_database" "orders" {
  name     = "orders"
  instance = google_sql_database_instance.orders.name
}

resource "google_sql_user" "orders_svc" {
  # Cloud SQL IAM users for service accounts drop the .gserviceaccount.com suffix.
  name     = trimsuffix(google_service_account.orders.email, ".gserviceaccount.com")
  instance = google_sql_database_instance.orders.name
  type     = "CLOUD_IAM_SERVICE_ACCOUNT"
}

resource "google_project_iam_member" "orders_sql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.orders.email}"
}

resource "google_project_iam_member" "orders_sql_login" {
  project = var.project_id
  role    = "roles/cloudsql.instanceUser"
  member  = "serviceAccount:${google_service_account.orders.email}"
}

# The order lifecycle as events. Consumers react; the order path never waits on them.
resource "google_pubsub_topic" "order_events" {
  name                       = "order-events"
  message_retention_duration = "604800s" # 7 days, so a consumer can replay
  depends_on                 = [google_project_service.apis]
}

resource "google_pubsub_topic" "order_events_dead" {
  name = "order-events-dead-letter"
}

resource "google_pubsub_topic_iam_member" "orders_publishes" {
  topic  = google_pubsub_topic.order_events.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:${google_service_account.orders.email}"
}

resource "google_pubsub_subscription" "billing" {
  name                         = "billing"
  topic                        = google_pubsub_topic.order_events.id
  ack_deadline_seconds         = 60
  enable_message_ordering      = true # ordered per order ID, the ordering key
  enable_exactly_once_delivery = true

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.order_events_dead.id
    max_delivery_attempts = 5
  }
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }
}

resource "google_pubsub_subscription_iam_member" "billing_reads" {
  subscription = google_pubsub_subscription.billing.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:${google_service_account.billing.email}"
}

# Pub/Sub's own service agent must be able to move a message to the dead-letter topic.
resource "google_pubsub_topic_iam_member" "dead_letter_publish" {
  topic  = google_pubsub_topic.order_events_dead.name
  role   = "roles/pubsub.publisher"
  member = "serviceAccount:service-${data.google_project.this.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_subscription_iam_member" "dead_letter_ack" {
  subscription = google_pubsub_subscription.billing.name
  role         = "roles/pubsub.subscriber"
  member       = "serviceAccount:service-${data.google_project.this.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

# Orders: the public edge of the slice, reached through the load balancer and the strangler router.
resource "google_cloud_run_v2_service" "orders" {
  name                = "orders"
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"
  deletion_protection = false

  template {
    service_account = google_service_account.orders.email
    containers {
      image = var.orders_image
      env {
        name  = "PRICING_URL"
        value = google_cloud_run_v2_service.pricing.uri
      }
      env {
        name  = "ORDER_EVENTS_TOPIC"
        value = google_pubsub_topic.order_events.id
      }
      env {
        name  = "DB_INSTANCE"
        value = google_sql_database_instance.orders.connection_name
      }
      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
    }
    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.orders.connection_name]
      }
    }
  }
  depends_on = [google_project_iam_member.orders_sql_client]
}

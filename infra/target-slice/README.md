# infra/target-slice: the first strangler slice on Google Cloud

A sketch of where the simulated Lone Star Foodservice order system goes after the
modernization: the first slice of a strangler migration, pricing and order capture.
It complements `infra/` one level up, which deploys the harness itself.

`terraform fmt` and `terraform validate` pass with Terraform 1.9.8 and the Google
provider 6.50.0. **Nothing here has been applied to a real project.**

## What it declares

| Resource | Why |
| --- | --- |
| Service accounts `pricing-svc`, `orders-svc`, `billing-svc` | One identity per service, each with only the grants below |
| Cloud Run service `pricing` | The translated ORDPRICE rules. Internal ingress only |
| `roles/run.invoker` on `pricing` for `orders-svc` only | IAM decides who may call pricing, before any code runs |
| Cloud SQL for PostgreSQL 16, `REGIONAL` | Orders data, with a standby in a second zone and point-in-time recovery |
| IAM database authentication, a `CLOUD_IAM_SERVICE_ACCOUNT` user | The orders service logs in as itself; no database password |
| Pub/Sub topic `order-events` | OrderPlaced events, published by orders only |
| Subscription `billing` | Ordered per order ID, exactly-once delivery, retry backoff |
| Topic `order-events-dead` | Dead letters after 5 delivery attempts, with the Pub/Sub service agent's grants |
| Cloud Run service `orders` | Order capture, behind an internal load balancer |

## The shape

```
orders (Cloud Run)  --sync, IAM-authenticated-->  pricing (Cloud Run, internal only)
orders              --writes-->                   Cloud SQL for PostgreSQL
orders              --publishes OrderPlaced-->    Pub/Sub order-events
billing             <--pull subscription--        order-events (dead letters after 5 tries)
```

Pricing is synchronous because the price must be right at the moment of the order.
Everything downstream of the order is an event.

## Check it

```
cd infra/target-slice
terraform init -backend=false
terraform fmt -check
terraform validate
```

## What it leaves out

The load balancer in front of orders, the transactional outbox relay, the strangler
router and the CDC path from the legacy. Those come next; this slice shows identity,
data and messaging decisions in code.

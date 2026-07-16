# Docker Compose: Defining Multi-Container Applications

Docker Compose is a tool for defining and running an application that is made up
of several cooperating containers. Instead of typing a long `docker run` command
for each container and wiring them together by hand, you describe the entire
application declaratively in a single YAML file and manage it as one unit. This
document covers the structure of the Compose file, how individual services are
defined, how startup dependencies are expressed, and how Compose handles
networks and volumes.

## The Compose file

By convention the file is named `compose.yaml`, and the command line tool reads
it from the current directory. The top-level document is organised into a small
number of keys, the most important of which is `services`. Each entry under
`services` describes one container that Compose will manage. Additional top-level
keys such as `volumes` and `networks` declare named resources that services can
reference and share.

```yaml
services:
  web:
    build: .
    ports:
      - "8080:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/app
    depends_on:
      - db
  db:
    image: postgres:16
    environment:
      - POSTGRES_PASSWORD=postgres
    volumes:
      - db-data:/var/lib/postgresql/data

volumes:
  db-data:
```

Running `docker compose up` reads this file, creates any required networks and
volumes, builds or pulls the necessary images, and starts one container per
service. Because the whole application is described in one place, a colleague can
reproduce the exact same environment by cloning the repository and running a
single command.

## Service definitions

Each service is a named block that tells Compose how to create its container. A
service either builds an image from a local `Dockerfile` using the `build` key or
pulls a prebuilt image named by the `image` key. Beyond choosing the image, the
service block collects the runtime options you would otherwise pass as flags to
`docker run`: `ports` publishes container ports to the host, `environment` sets
environment variables, `volumes` attaches storage, and `command` overrides the
default process.

The `ports` mapping deserves attention because it uses the same
`host:container` order as the Docker CLI. In the example above, `"8080:8000"`
means traffic arriving on port 8080 of the host is forwarded to port 8000 inside
the web container. Ports that are only used for communication between services do
not need to be published to the host at all, since services on the same Compose
network can already reach each other directly.

## Service discovery between containers

Compose automatically creates a dedicated network for the application and
attaches every service to it. On this network each service is reachable by its
service name, which Compose registers in an embedded DNS resolver. That is why
the `web` service in the example connects to the database using the hostname
`db` rather than an IP address: `db` resolves to the current address of the
database container regardless of restarts. This built-in name resolution removes
the need to hardcode addresses and is one of the main conveniences Compose
provides over managing containers individually.

## Startup order and dependencies

Multi-container applications frequently require one service to start before
another. The `depends_on` option controls the startup order of services, telling
Compose to start the listed dependencies first and to stop them last. In the
example the web service depends on `db`, so Compose starts the database container
before the web container.

It is important to understand the limit of this guarantee. By default
`depends_on` waits only until the dependency's container has been started, not
until the process inside it is actually ready to accept connections. A database
container can be running while PostgreSQL is still initialising, so the
application may still need to retry its first connections. To wait for genuine
readiness, you attach a health check to the dependency and use the long form of
`depends_on` with a `condition` of `service_healthy`, which makes Compose hold
the dependent service until the health check passes.

```yaml
  web:
    build: .
    depends_on:
      db:
        condition: service_healthy
  db:
    image: postgres:16
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "postgres"]
      interval: 5s
      retries: 5
```

## Networks and volumes

Named volumes declared at the top level persist data beyond the lifetime of any
single container. In the first example the `db-data` volume is mounted into the
PostgreSQL data directory, so the database contents survive `docker compose down`
followed by a fresh `up`. Anonymous, in-container storage would be discarded when
the container is recreated, which is exactly what you do not want for a database.

Networks can likewise be declared explicitly when the default single network is
not sufficient. Defining multiple networks lets you isolate groups of services
from one another, for example placing a database on a private backend network
that the public-facing web tier can reach but that is not otherwise exposed.
Together, service definitions, dependency ordering, service-name discovery, and
declared volumes and networks let a single Compose file capture a complete
multi-container application in a form that is easy to version, share, and run.

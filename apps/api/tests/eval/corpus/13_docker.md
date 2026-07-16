# Docker: Images, Layers, and Containers

Docker is a platform for packaging an application together with its runtime
dependencies into a portable unit called an image, then executing that image as
an isolated process called a container. The value of the model comes from a
strict separation between the immutable build artifact and the ephemeral running
instance. This document explains how images are structured from stacked layers,
how a Dockerfile produces those layers, and how a container is created from an
image at runtime.

## Images and the union filesystem

A Docker image is a read-only template composed of an ordered stack of
filesystem layers. Every layer records only the changes it makes relative to the
layer beneath it: files that were added, files that were modified, and files
that were deleted. Because a layer captures a delta rather than a full copy of
the filesystem, common base layers can be shared between many images on the same
host, which saves both disk space and network transfer time.

To present this stack as a single coherent directory tree to the running
process, Docker relies on a union filesystem driver such as OverlayFS. The driver
merges the layers so that upper layers shadow files of the same path in lower
layers. From inside the container the result looks like an ordinary root
filesystem, even though it is assembled on the fly from several independent
layers. The layers themselves are content-addressable: each is identified by a
digest computed from its contents, so an identical layer is stored only once.

## The Dockerfile and layer caching

A Dockerfile is a plain text file containing the ordered set of instructions
used to assemble an image. When you run `docker build`, the daemon reads the file
from top to bottom and executes the instructions one at a time. A key property
of this process is that each instruction in a Dockerfile creates a new image
layer stacked on top of the previous result. Instructions such as `RUN`, `COPY`,
and `ADD` produce filesystem changes and therefore materialise a layer, while
metadata-only instructions such as `ENV`, `LABEL`, and `EXPOSE` contribute
configuration without adding meaningful filesystem content.

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
ENTRYPOINT ["uvicorn", "app.main:app"]
CMD ["--host", "0.0.0.0", "--port", "8000"]
```

The build cache is what makes this layer model efficient. For each instruction
the daemon computes a cache key from the instruction text and the state of its
inputs. If a matching layer already exists, the daemon reuses it instead of
executing the instruction again. As soon as one instruction misses the cache,
every instruction after it must be rebuilt, because each later layer depends on
the exact result of the one before it. This is why dependency installation is
placed before copying application source: requirements change infrequently, so
the expensive `pip install` layer stays cached while source edits invalidate
only the final, cheap `COPY` layer.

The distinction between `ENTRYPOINT` and `CMD` frequently causes confusion.
`ENTRYPOINT` defines the executable that always runs, while `CMD` supplies the
default arguments that a user can override on the command line. Used together, as
above, the container behaves like a configurable command whose defaults can be
replaced without editing the image.

## Containers as running instances

A container is a running, or stopped, instance created from an image. When a
container starts, Docker adds a single thin writable layer on top of the stack of
read-only image layers. Every file the process writes goes into this writable
layer. Reads fall through to the image layers underneath, but the first write to
an existing file triggers a copy-on-write operation: the file is copied up into
the writable layer and modified there, leaving the underlying image layer
untouched. This is what lets many containers share the same immutable image while
each maintains its own independent changes.

Because the writable layer lives and dies with the container, any data written
inside it is lost when the container is removed. Durable state must therefore be
kept outside the layer stack, in a named volume or a bind mount, both of which
are mounted into the container's filesystem but stored on the host and managed
separately from the image. This separation of immutable image from disposable
container is the core discipline of the Docker model.

```bash
docker build -t myapp:1.0 .
docker run -d --name web -p 8080:8000 myapp:1.0
docker ps
docker logs web
```

## Tags, registries, and distribution

Images are named using a `repository:tag` reference, for example
`myapp:1.0` or `nginx:1.27-alpine`. The tag is a human-friendly pointer that can
be moved to a different underlying image over time, which is why the same tag can
resolve to different content on different days. The tag `latest` carries no
special meaning to the daemon; it is simply the default tag applied when none is
given, and it is not automatically the newest version.

A registry is a service that stores and distributes images. `docker push`
uploads the layers your host holds to a registry, and `docker pull` downloads the
layers it is missing. Because layers are content-addressed and deduplicated, a
pull transfers only the layers not already present locally, and a push uploads
only layers the registry has not seen. This layer-level deduplication is what
keeps image distribution fast even as the number of tagged images grows.

Understanding images, layers, and containers as three distinct concepts, the
immutable stacked template, the individual delta that composes it, and the
disposable writable instance, is the foundation for everything else in the Docker
workflow, from writing efficient Dockerfiles to reasoning about where persistent
data actually lives.

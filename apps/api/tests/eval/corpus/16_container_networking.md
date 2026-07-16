# Container Networking: Bridges, Overlays, CNI, and Port Mapping

Container networking is the set of mechanisms that give containers their own
network identity and let them communicate with each other, with the host, and
with the outside world. The building blocks come from the Linux kernel, and the
higher-level tools, Docker network drivers, overlay networks, and the Container
Network Interface, arrange those blocks into usable models. This document walks
from the kernel primitives up to multi-host networking and port publishing.

## Network namespaces and veth pairs

The foundation of container networking is the network namespace. A network
namespace is an isolated copy of the kernel's networking stack, with its own
interfaces, routing table, and firewall rules. When a container starts, it is
placed in a fresh network namespace, so from inside it appears to have a private
network all to itself, including its own loopback interface.

To connect that isolated namespace to anything else, the kernel uses a virtual
Ethernet device, known as a veth pair. A veth pair behaves like a virtual cable:
it is created as two linked interfaces, and a packet sent into one end emerges
from the other. One end is placed inside the container's namespace and becomes
its `eth0`, while the other end stays in the host namespace and is attached to a
bridge. This pairing is what carries traffic across the namespace boundary.

## The default bridge network

On a single host the default Docker driver is the bridge network. Docker creates
a virtual switch on the host, conventionally named `docker0`, and attaches the
host end of every container's veth pair to it. Containers on the same bridge can
therefore exchange packets as if they were plugged into a common switch, each
having received a private IP address from the bridge's subnet.

```bash
docker network create --driver bridge backend
docker run -d --name db --network backend postgres:16
docker run -d --name web --network backend -p 8080:8000 myapp:1.0
docker network inspect backend
```

A user-defined bridge, created as above, adds an important feature over the
built-in default: it provides automatic DNS resolution by container name. On a
user-defined bridge the `web` container can connect to `db` by name, whereas on
the legacy default bridge only IP addresses work. For traffic leaving the host,
the bridge relies on the kernel's network address translation: outbound packets
have their source address rewritten to the host's address, so containers with
private IPs can still reach external networks.

## Overlay networks for multi-host communication

A single bridge only connects containers on one machine. To let containers
running on different machines talk to each other as though they were on the same
LAN, Docker provides the overlay driver. An overlay network spans multiple Docker
hosts by encapsulating each container packet inside a second packet, typically
using VXLAN, and sending that outer packet across the physical network between
hosts. The receiving host strips the encapsulation and delivers the original
packet to the destination container.

From the container's point of view nothing special is happening: it sees a flat
network and a single subnet shared with peers that may physically live on other
nodes. The overlay driver, together with a distributed key-value store that
tracks which container lives on which host, hides the tunnelling entirely. This
is the model that lets a cluster present one logical network to a distributed
application.

## The Container Network Interface

Kubernetes does not use Docker's networking drivers directly. Instead it defines
a specification called the Container Network Interface, or CNI, which standardises
how networking is configured for a container. When a pod is created, the kubelet
invokes a CNI plugin as an executable, passing it the container's namespace and
expecting it to set up interfaces and addresses and then return the result as
JSON.

This plugin model is deliberately pluggable, so different implementations can
satisfy the same contract. A CNI plugin is responsible for allocating an IP
address to the pod and wiring its namespace into the cluster network, and popular
implementations such as Calico, Flannel, and Cilium each do this differently,
using routing, overlays, or eBPF while presenting the same interface to
Kubernetes. The result is that every pod receives a routable address and any pod
can reach any other pod without network address translation, which is the flat
networking model Kubernetes requires.

## Port mapping and publishing

Containers on a private network are not reachable from outside the host unless a
port is explicitly published. Port mapping, configured with the `-p` flag or the
`ports` key in Compose, tells the container runtime to forward traffic arriving
on a host port to a port inside the container.

```bash
docker run -d -p 8080:8000 myapp:1.0
```

Here the runtime installs a network address translation rule so that connections
to port 8080 on the host are rewritten and delivered to port 8000 in the
container. The two numbers are independent: many containers can each expose port
8000 internally while being published on distinct host ports, which is how a
single machine runs several instances of the same image side by side. Only the
published ports are reachable externally; every other container port remains
private to its network, available to peer containers but invisible to the host's
neighbours. Understanding this chain, from namespaces and veth pairs, through
bridges and overlays, to CNI and port publishing, explains how a packet actually
finds its way to a process running inside a container.

# Kubernetes: Pods, Deployments, Services, and Scheduling

Kubernetes is an orchestration system that runs containerised workloads across a
cluster of machines. Rather than starting containers by hand on individual
hosts, an operator declares the desired state of the system, and a set of control
plane components continuously works to make the actual state match. This document
describes the core objects a workload is built from, pods, deployments, and
services, and explains how the scheduler decides where work runs.

## Pods: the smallest deployable unit

The pod is the smallest object that Kubernetes can create and manage. A pod wraps
one or more containers that are always co-located and co-scheduled on the same
node. Containers in a pod share a single network namespace, so they reach one
another over `localhost` and share a single cluster-internal IP address. They can
also share storage volumes mounted into the pod. In the common case a pod holds
exactly one application container, but the multi-container pattern is used for
tightly coupled helpers such as a sidecar that ships logs or a proxy that
terminates TLS.

Pods are deliberately treated as disposable. They are never healed in place; when
a pod dies it is replaced by a brand new pod with a new identity and a new IP
address. This is why workloads almost never create bare pods directly, and
instead rely on a controller that manages pods on their behalf.

## Deployments and ReplicaSets

A Deployment is the controller most commonly used to run a stateless
application. It manages a ReplicaSet, which in turn ensures that a specified
number of identical pod replicas are running at all times. If a node fails or a
pod crashes, the ReplicaSet notices the shortfall and creates replacements until
the observed count matches the declared `replicas` field.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
    spec:
      containers:
        - name: web
          image: myapp:1.0
          ports:
            - containerPort: 8000
```

The Deployment's real power is in how it handles change. When you update the pod
template, for example by bumping the image tag, the Deployment performs a rolling
update: it creates a new ReplicaSet, gradually scales it up while scaling the old
one down, and keeps the application available throughout. Because it records the
history of these ReplicaSets, a Deployment can also roll back to a previous
revision if a release turns out to be faulty.

## Services and stable networking

Because pods are ephemeral and their IP addresses change on every restart, they
cannot be addressed directly by clients. A Service solves this by providing a
stable endpoint in front of a changing set of pods. Concretely, a Kubernetes
Service provides a stable virtual IP, called the ClusterIP, that stays constant
for the life of the Service. The Service uses a label selector to track which
pods currently back it, and it load-balances incoming connections across those
healthy pods.

There are several Service types. A ClusterIP Service is reachable only from
inside the cluster and is the default. A NodePort Service additionally opens the
same port on every node so external traffic can reach the pods, and a
LoadBalancer Service asks the cloud provider to provision an external load
balancer that forwards to the NodePort. In every case the Service decouples
callers from the individual pods, so pods can be created and destroyed freely
without breaking the clients that depend on them.

## The scheduler and node assignment

New pods are created in an unassigned state, meaning no node has been chosen for
them yet. The scheduler is the control plane component responsible for closing
this gap: the Kubernetes scheduler assigns each pod to a node through a two-phase
decision. In the filtering phase it discards nodes that cannot run the pod at
all, for example nodes without enough allocatable CPU or memory, nodes that do
not satisfy the pod's node selector, or nodes whose taints the pod does not
tolerate. In the scoring phase it ranks the remaining feasible nodes and picks
the one with the highest score, spreading load and honouring affinity rules.

```bash
kubectl apply -f deployment.yaml
kubectl get pods -o wide
kubectl describe pod web-6d4cf56db6-abcde
kubectl scale deployment web --replicas=5
```

Once a node is chosen, the scheduler records the binding, and the kubelet running
on that node takes over. The kubelet is the per-node agent that watches for pods
assigned to its node, pulls the required images, and instructs the container
runtime to start the containers. It then reports pod status back to the control
plane and runs the liveness and readiness probes that determine whether a pod is
healthy and ready to receive traffic.

## How the pieces fit together

A typical stateless workload therefore layers these objects. The Deployment
declares how many replicas should exist and manages rollouts. The ReplicaSet it
owns keeps that number of pods alive. The scheduler places each new pod on a
suitable node, and the kubelet on that node actually runs it. Finally a Service
sits in front of the whole set, giving clients one stable address regardless of
which pods happen to exist at any moment. Each layer has a single clear
responsibility, and together they turn a declared desired state into a running,
self-healing system.

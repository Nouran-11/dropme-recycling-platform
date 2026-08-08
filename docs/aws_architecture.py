"""Render the AWS deployment topology to docs/aws-architecture.png.

Run:  uv run --with diagrams python docs/aws_architecture.py
Requires graphviz on the system.
"""

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import EC2, EC2ElasticIpAddress
from diagrams.aws.general import Users
from diagrams.aws.storage import EBS

with Diagram(
    "Drop Me — AWS deployment",
    filename="docs/aws-architecture",
    outformat="png",
    show=False,
):
    operator = Users("Operator / RVM")

    with Cluster("AWS · eu-north-1"):
        with Cluster("Default VPC — public subnet"):
            eip = EC2ElasticIpAddress("16.16.21.54 (sslip.io, TLS)")
            with Cluster("Security group: 80/443 open, 22 my IP only"):
                ec2 = EC2("m7i-flex.large — Ubuntu 24.04")
            ebs = EBS("30 GB gp3 — pgdata + backups")

    engineer = Users("Engineer")

    operator >> Edge(label="HTTPS") >> eip
    eip >> ec2
    ec2 >> ebs
    engineer >> Edge(label="SSH :22 / tunnel to Grafana", style="dashed") >> ec2

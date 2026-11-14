# AWS Free Tier Deployment Guide: `gemini-cost-arbiter-mcp`

This guide details how to deploy the **Gemini Autonomous Cloud-Cost Arbiter MCP Server** onto **100% Free AWS Infrastructure** without incurring cloud charges.

---

## 1. AWS Free Tier Deployment Options Summary

| Deployment Architecture | AWS Free Tier Allocation | Estimated Monthly Cost | Best For |
|:---|:---|:---:|:---|
| **Option A: EC2 Free Tier Host (`t3.micro` / `t4g.small`)** | **750 hours/month** of Linux `t2.micro` or `t3.micro` (or `t4g.small` trial). | **$0.00** | Continuous MCP Server hosting with persistent SQLite ledger via Docker Compose. |
| **Option B: Serverless AWS Lambda + Function URL** | **1,000,000 free requests/month** and 3,200,000 seconds of compute time free every month forever. | **$0.00** | Zero-server, pay-nothing-when-idle deployment with built-in public HTTPS endpoint. |
| **Option C: AWS App Runner** | Supported via container image from Amazon ECR Public. | **$0.00** (within trial) | Managed container deployment without managing VMs or OS patches. |

---

## 2. Option A: Turnkey EC2 Free Tier Deployment (`t3.micro` / `t4g.small`)

### Step 1: Launch Free Tier EC2 Instance
1. Open the [AWS EC2 Console](https://console.aws.amazon.com/ec2).
2. Click **Launch Instance**:
   * **Name:** `gemini-cost-arbiter-mcp`
   * **AMI:** Amazon Linux 2023 AMI (Free Tier eligible)
   * **Instance Type:** `t3.micro` (2 vCPU, 1 GiB RAM) or `t4g.small` (ARM64)
   * **Key Pair:** Select or create your SSH key pair.
   * **Network / Security Group:**
     * Allow SSH (Port 22) from your IP.
     * Allow Custom TCP (Port 8000) from anywhere (`0.0.0.0/0`) or your restricted agent IP.
   * **Storage:** 20 GiB gp3 (up to 30 GiB is Free Tier eligible).
3. Click **Launch Instance**.

### Step 2: Run Turnkey Deployment Script
SSH into your instance and run the one-command deployment script:

```bash
# Connect to instance
ssh -i your-key.pem ec2-user@<YOUR-EC2-PUBLIC-IP>

# Clone repository
git clone https://github.com/your-org/gemini-cost-arbiter-mcp.git
cd gemini-cost-arbiter-mcp

# Run the automated deployment script
chmod +x deploy/aws-free-tier/deploy-ec2.sh
./deploy/aws-free-tier/deploy-ec2.sh
```

### Step 3: Configure Credentials & Start Container
The script will prompt you for your `GEMINI_API_KEY`:

```bash
nano .env
# Set GEMINI_API_KEY=your_key_here

# Launch container in background
docker compose -f deploy/aws-free-tier/docker-compose.prod.yml up -d
```

### Step 4: Verify Deployment
```bash
# Verify health probe
curl http://localhost:8000/health
# Response: {"status":"healthy","service":"gemini-cost-arbiter-mcp"}

# Check container logs
docker compose -f deploy/aws-free-tier/docker-compose.prod.yml logs -f
```

---

## 3. Option B: Serverless AWS Lambda Container with Function URL (100% Free Forever)

For true serverless deployment where you never manage an EC2 instance and pay **zero dollars** when the server is idle, use the AWS Lambda Web Adapter:

### Step 1: Build & Push Lambda Container Image
```bash
# Log in to your Amazon ECR private repository
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com

# Build using Lambda Adapter Dockerfile
docker build -f deploy/aws-free-tier/lambda-adapter/Dockerfile -t gemini-cost-arbiter-lambda .

# Tag and push
docker tag gemini-cost-arbiter-lambda:latest <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/gemini-cost-arbiter:latest
docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/gemini-cost-arbiter:latest
```

### Step 2: Create Lambda Function with Function URL
```bash
# Create Lambda Function
aws lambda create-function \
    --function-name gemini-cost-arbiter-mcp \
    --package-type Image \
    --code ImageUri=<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/gemini-cost-arbiter:latest \
    --role arn:aws:iam::<ACCOUNT_ID>:role/lambda-execution-role \
    --timeout 60 \
    --memory-size 512 \
    --environment "Variables={GEMINI_API_KEY=your_key,DEFAULT_MODEL=gemini-3.8-flash-high}"

# Enable public Function URL (HTTPS endpoint)
aws lambda create-function-url-config \
    --function-name gemini-cost-arbiter-mcp \
    --auth-type NONE

# Grant public access to Function URL
aws lambda add-permission \
    --function-name gemini-cost-arbiter-mcp \
    --statement-id FunctionURLAllowPublicAccess \
    --action lambda:InvokeFunctionUrl \
    --principal "*" \
    --function-url-auth-type NONE
```

Your public MCP SSE endpoint is now live at:
`https://<FUNCTION_URL_ID>.lambda-url.us-east-1.on.aws/sse`

---

## 4. Lambda Ephemeral Storage & Distributed Ledger Architecture

> [!WARNING]
> **Ephemeral Storage Limitation on AWS Lambda:**  
> AWS Lambda microVM instances use an ephemeral `/tmp` directory that is discarded during cold starts and isolated across concurrent executions. If you rely on `--db-path /tmp/finops.db`, ledger state is split-brain across concurrent microVMs.
> 
> **Enterprise Production Patterns for Lambda Durability:**
> 1. **Amazon EFS Mount:** Attach an Amazon Elastic File System (EFS) access point to the Lambda function. Set `DB_PATH=/mnt/efs/finops.db` for persistent, concurrent-safe SQLite storage.
> 2. **S3 State Synchronization:** Configure a pre-shutdown or post-request hook uploading `/tmp/finops.db` to an encrypted private S3 bucket.
> 3. **EC2 Option A Preference:** For workloads requiring seamless local SQLite ledger durability without extra AWS services, **Option A (EC2 Free Tier Host)** is the recommended architecture.

---

## 5. AWS Free Tier Zero-Cost Protection Rules

1. **Set Up an AWS Zero-Spend Budget:**
   * Go to **AWS Budgets** in the AWS Console.
   * Click **Create budget** -> **Zero spend budget**.
   * Enter your email to receive an instant alarm if spending exceeds $0.01.
2. **Keep EC2 Storage $\le$ 30 GB:** AWS gives 30 GB of gp2/gp3 storage free across all EBS volumes.
3. **Stop or Terminate When Not in Use:** If testing for short periods, `docker compose down` stops the workload cleanly.

---

## 6. Security Advisory: MCP API Key & Access Log Masking

> [!CAUTION]
> **Query Parameter Plaintext Logging Hazard:**  
> The MCP Server-Sent Events (SSE) server supports three authentication mechanisms:
> 1. `Authorization: Bearer <key>` header (RFC 6750) — **Recommended for automated SRE agents & backend gateways**
> 2. `X-API-Key: <key>` header — **Recommended for API gateways & tools**
> 3. `?apiKey=<key>` query parameter — **Supported exclusively for browser `EventSource` clients**
> 
> **Production Logging Risk:** Standard web servers, reverse proxies (Nginx, Envoy, Traefik), and AWS Application Load Balancers (ALB) record full request URLs—including query parameters—in plaintext access logs by default. Passing secrets via `?apiKey=` will expose `MCP_API_KEY` in CloudWatch, ALB access logs, and ingress controller telemetry.
> 
> **SecOps Mandate:**
> - Automated agents (Cursor, Claude Desktop, Antigravity) must strictly use `Authorization: Bearer` or `X-API-Key` headers.
> - When using `?apiKey=` for browser connections, reverse proxies MUST be configured to mask or strip query strings in access logs (e.g., Nginx `log_format combined_masked '$remote_addr ... "$uri" ...'`).

# AWS Production Deployment Guide (`docs/DEPLOYMENT_AWS.md`)

**Target Environment:** Amazon Web Services (AWS) — EC2 Free Tier (`t3.micro`/`t4g.small`) & AWS Lambda Web Adapter  
**Governance:** [`GEMINI.md`](../GEMINI.md) | [`Enterprise_Blueprint.md`](../Enterprise_Blueprint.md)  
**Assets:** [`deploy/aws/deploy-ec2.sh`](../deploy/aws/deploy-ec2.sh), [`deploy/aws/docker-compose.prod.yml`](../deploy/aws/docker-compose.prod.yml), [`deploy/aws/lambda-adapter/Dockerfile`](../deploy/aws/lambda-adapter/Dockerfile)

---

## 1. Deployment Options & Architecture

| Option | Compute | Persistence | Estimated Monthly Cost | Best For |
|:---|:---|:---|:---:|:---|
| **Option A: EC2 Free Tier** | `t3.micro` / `t4g.small` (Docker Compose) | EBS `/app/data/finops.db` (SQLite WAL) | **$0.00** (750 hrs/mo Free Tier) | Continuous SSE MCP server with local SQLite WAL ledger |
| **Option B: AWS Lambda** | Container Image + Lambda Web Adapter | Amazon EFS (`/mnt/efs/finops.db`) or `/tmp` | **$0.00** (1M requests/mo Free Tier) | Serverless scale-to-zero HTTPS Function URL |

---

## 2. IAM Least-Privilege Policies & Secrets (AWS SSM Parameter Store)

Store production secrets as `SecureString` parameters in AWS SSM Parameter Store (never bake secrets into Docker images or `.env` files committed to git):

```bash
aws ssm put-parameter --name "/gemini-cost-arbiter/GEMINI_API_KEY" --value "<YOUR_GEMINI_API_KEY>" --type "SecureString" --overwrite
aws ssm put-parameter --name "/gemini-cost-arbiter/MCP_API_KEY" --value "$(openssl rand -hex 32)" --type "SecureString" --overwrite
aws ssm put-parameter --name "/gemini-cost-arbiter/PLAN_SIGNING_SECRET" --value "$(openssl rand -hex 32)" --type "SecureString" --overwrite
```

Attach an IAM Instance Profile / Lambda Execution Role with least-privilege SSM and CloudWatch permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowSSMParameterRead",
      "Effect": "Allow",
      "Action": ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"],
      "Resource": "arn:aws:ssm:*:*:parameter/gemini-cost-arbiter/*"
    },
    {
      "Sid": "AllowCloudWatchLogging",
      "Effect": "Allow",
      "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
      "Resource": "arn:aws:logs:*:*:log-group:/aws/gemini-cost-arbiter/*"
    }
  ]
}
```

---

## 3. Option A: Turnkey EC2 Free Tier Deployment

1. Launch an Amazon Linux 2023 (`t3.micro` or `t4g.small`) instance with a Security Group allowing SSH (`22`) from your IP and HTTPS (`443` via ALB/Nginx) or port `8000` from authorized agent CIDRs.
2. Run the automated setup script and launch the production container:

```bash
git clone https://github.com/jayzamindar/gemini-cost-arbiter-mcp.git
cd gemini-cost-arbiter-mcp
chmod +x deploy/aws/deploy-ec2.sh
./deploy/aws/deploy-ec2.sh

# Populate .env (ENVIRONMENT=production, REQUIRE_AUTH=true, MCP_API_KEY, PLAN_SIGNING_SECRET >= 32 chars, GEMINI_API_KEY)
docker compose -f deploy/aws/docker-compose.prod.yml up -d
```

3. Verify the live health probe:

```bash
curl -f http://localhost:8000/health
# Expected: {"status":"healthy","service":"gemini-cost-arbiter-mcp"}
```

---

## 4. Option B: Serverless AWS Lambda Container (ECR + Function URL)

```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com
docker build -f deploy/aws/lambda-adapter/Dockerfile -t gemini-cost-arbiter-lambda .
docker tag gemini-cost-arbiter-lambda:latest <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/gemini-cost-arbiter:latest
docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/gemini-cost-arbiter:latest

aws lambda create-function \
    --function-name gemini-cost-arbiter-mcp \
    --package-type Image \
    --code ImageUri=<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/gemini-cost-arbiter:latest \
    --role arn:aws:iam::<ACCOUNT_ID>:role/ArbiterLambdaRole \
    --timeout 60 \
    --memory-size 512 \
    --environment "Variables={ENVIRONMENT=production,REQUIRE_AUTH=true,MAX_PAYLOAD_BYTES=10485760,DB_PATH=/tmp/finops.db}"
```

> [!WARNING]
> Lambda `/tmp` is ephemeral across microVMs. For multi-invocation SQLite WAL durability on Lambda, mount **Amazon EFS** at `/mnt/efs` and set `DB_PATH=/mnt/efs/finops.db`.

---

## 5. Runtime & MCP Verification

- Default reasoning model: `DEFAULT_MODEL=gemini-3.8-flash-high` with `clean_gemini_schema()` Protobuf sanitization.
- Smoke-test locally with `gemini-cost-arbiter analyze -f sample_telemetry.json` and inspect MCP resources (`finops://audit/ledger`, `finops://policies/risk-matrix`, `finops://config/instance-mappings`).

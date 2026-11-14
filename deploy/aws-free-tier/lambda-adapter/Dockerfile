# ==============================================================================
# AWS Lambda Serverless Container with Lambda Web Adapter (100% Free Forever)
# ==============================================================================
FROM public.ecr.aws/awslabs/aws-lambda-adapter:0.8.4 AS lambda_adapter

FROM python:3.13-slim

# Copy the AWS Lambda Web Adapter binary into the extensions directory
COPY --from=lambda_adapter /lambda-adapter /opt/extensions/lambda-adapter

WORKDIR /app

# Install dependencies and package
COPY pyproject.toml requirements.txt README.md /app/
COPY config/ /app/config/
COPY src/ /app/src/
COPY app/ /app/app/

RUN pip install --no-cache-dir --upgrade pip setuptools && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir .

# Configure Lambda Web Adapter environment
ENV PORT=8000
ENV AWS_LWA_PORT=8000
ENV AWS_LWA_READINESS_CHECK_PATH=/health
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000
ENV DB_PATH=/tmp/finops.db

EXPOSE 8000

CMD ["gemini-cost-arbiter", "run-mcp", "--transport", "sse", "--host", "0.0.0.0", "--port", "8000", "--db-path", "/tmp/finops.db"]

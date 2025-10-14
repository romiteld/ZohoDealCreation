# Azure Service Bus Configuration

## Service Bus Details

**Namespace:** `wellintakebus-standard`
**Resource Group:** `TheWell-Infra-East`
**Location:** East US
**Tier:** Standard
**Endpoint:** `https://wellintakebus-standard.servicebus.windows.net:443/`

## Connection String

```bash
AZURE_SERVICE_BUS_CONNECTION_STRING="Endpoint=sb://wellintakebus-standard.servicebus.windows.net/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=<REDACTED>"
```

## Queues Configuration

### 1. teams-digest-requests
- **Purpose:** Digest generation requests (longer processing time)
- **Max Size:** 1024 MB
- **Lock Duration:** PT5M (5 minutes)
- **Max Delivery Count:** 3
- **Dead Lettering on Message Expiration:** Enabled
- **Batched Operations:** Enabled
- **Default TTL:** 7 days
- **Queue URL:** `sb://wellintakebus-standard.servicebus.windows.net/teams-digest-requests`

### 2. teams-nlp-queries
- **Purpose:** Natural language processing queries (quick processing)
- **Max Size:** 1024 MB (minimum allowed in Standard tier)
- **Lock Duration:** PT2M (2 minutes)
- **Max Delivery Count:** 2
- **Dead Lettering on Message Expiration:** Enabled
- **Batched Operations:** Enabled
- **Default TTL:** 1 day
- **Queue URL:** `sb://wellintakebus-standard.servicebus.windows.net/teams-nlp-queries`

## KEDA Autoscaling Configuration

Add the following KEDA scaled objects to your Azure Container Apps configuration:

### For teams-digest-requests Queue

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: teams-digest-scaler
spec:
  scaleTargetRef:
    name: teams-bot
  minReplicaCount: 0
  maxReplicaCount: 10
  triggers:
  - type: azure-servicebus
    metadata:
      queueName: teams-digest-requests
      messageCount: "5"  # Scale up when 5 messages in queue
      connectionFromEnv: AZURE_SERVICE_BUS_CONNECTION_STRING
      namespace: wellintakebus-standard
```

### For teams-nlp-queries Queue

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: teams-nlp-scaler
spec:
  scaleTargetRef:
    name: teams-bot
  minReplicaCount: 1  # Keep 1 instance always running for quick response
  maxReplicaCount: 20
  triggers:
  - type: azure-servicebus
    metadata:
      queueName: teams-nlp-queries
      messageCount: "10"  # Scale up when 10 messages in queue
      connectionFromEnv: AZURE_SERVICE_BUS_CONNECTION_STRING
      namespace: wellintakebus-standard
```

## Azure Container Apps Environment Variables

Add these to your Container App configuration:

```bash
# In Azure Portal or via CLI
az containerapp update \
  --name teams-bot \
  --resource-group TheWell-Infra-East \
  --set-env-vars \
    AZURE_SERVICE_BUS_CONNECTION_STRING="Endpoint=sb://wellintakebus-standard.servicebus.windows.net/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=<REDACTED>" \
    AZURE_SERVICE_BUS_NAMESPACE="wellintakebus-standard" \
    AZURE_SERVICE_BUS_DIGEST_QUEUE="teams-digest-requests" \
    AZURE_SERVICE_BUS_NLP_QUEUE="teams-nlp-queries"
```

## Python SDK Usage Example

```python
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage
import os
import asyncio

CONNECTION_STRING = os.getenv("AZURE_SERVICE_BUS_CONNECTION_STRING")

async def send_to_queue(queue_name: str, message_body: dict):
    async with ServiceBusClient.from_connection_string(
        CONNECTION_STRING
    ) as servicebus_client:
        sender = servicebus_client.get_queue_sender(queue_name=queue_name)
        async with sender:
            message = ServiceBusMessage(
                body=json.dumps(message_body),
                content_type="application/json"
            )
            await sender.send_messages(message)

async def receive_from_queue(queue_name: str):
    async with ServiceBusClient.from_connection_string(
        CONNECTION_STRING
    ) as servicebus_client:
        receiver = servicebus_client.get_queue_receiver(
            queue_name=queue_name,
            max_wait_time=30
        )
        async with receiver:
            messages = await receiver.receive_messages(
                max_message_count=10,
                max_wait_time=5
            )
            for message in messages:
                # Process message
                print(f"Received: {str(message)}")
                await receiver.complete_message(message)
```

## Migration Notes

### From Basic to Standard Tier
- **Issue:** Azure Service Bus Basic tier cannot be directly upgraded to Standard tier
- **Solution:** Created new namespace `wellintakebus-standard` with Standard tier
- **Old Namespace:** `wellintakebus0903` (Basic tier) - can be deleted after migration
- **Migration Path:**
  1. Update application connection strings
  2. Test with new namespace
  3. Delete old namespace after verification

### Configuration Adjustments
- **teams-nlp-queries:** Originally requested 512 MB max size, but Standard tier minimum is 1024 MB
- **TTL Settings:** Added appropriate default message time-to-live for each queue
- **Dead Letter Queues:** Automatically created for both queues when dead lettering is enabled

## Monitoring and Metrics

Monitor queues via Azure Portal:
1. Navigate to Service Bus namespace
2. Select "Queues" from left menu
3. View metrics:
   - Active message count
   - Dead letter message count
   - Incoming/Outgoing messages per second
   - Server errors
   - User errors

## Security Best Practices

1. **Store connection string in Azure Key Vault:**
```bash
az keyvault secret set \
  --vault-name YourKeyVaultName \
  --name "ServiceBusConnectionString" \
  --value "Endpoint=sb://wellintakebus-standard.servicebus.windows.net/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=<REDACTED>"
```

2. **Use Managed Identity when possible** (for Azure Container Apps)
3. **Create queue-specific shared access policies** with minimal permissions
4. **Enable diagnostic logs** for auditing and troubleshooting

## Cleanup Commands

If you need to delete the old Basic tier namespace:
```bash
az servicebus namespace delete \
  --resource-group TheWell-Infra-East \
  --name wellintakebus0903
```
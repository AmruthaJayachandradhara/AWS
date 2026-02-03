import base64
import json
import os
import boto3
from datetime import datetime

# Initialize AWS Resources
dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')

# Environment Variables for Scalability
PATIENTS_TABLE = os.environ.get('PATIENTS_TABLE', 'Patients')
VITALS_TABLE = os.environ.get('VITALS_TABLE', 'Vitals')
ALERTS_TABLE = os.environ.get('ALERTS_TABLE', 'Alerts')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')

# Connect to DynamoDB Tables
vitals_table = dynamodb.Table(VITALS_TABLE)
alerts_table = dynamodb.Table(ALERTS_TABLE)

def classify_risk(hr, spo2, bp_sys):
    """
    Analyzes vital signs against medical thresholds.
    Source logic derived from project anomaly detection requirements.
    """
    # Critical Thresholds [cite: 23, 106, 109]
    if hr > 140 or spo2 < 86 or bp_sys > 180:
        return "critical"
    # Warning Thresholds [cite: 112]
    elif (120 < hr <= 140) or (86 <= spo2 < 92) or (160 < bp_sys <= 180):
        return "warning"
    else:
        return "normal"

def lambda_handler(event, context):
    """
    Main entry point for Kinesis stream processing[cite: 21, 135].
    """
    for record in event['Records']:
        # Decode Kinesis data [cite: 95]
        payload = base64.b64decode(record['kinesis']['data']).decode('utf-8')
        data = json.loads(payload)
        
        patient_id = data.get('patient_id')
        hr = data.get('hr')
        spo2 = data.get('spo2')
        bp_sys = data.get('bp_sys')
        timestamp = datetime.now().isoformat()

        # Step 1: Classify Risk Level
        risk_status = classify_risk(hr, spo2, bp_sys)

        # Step 2: Store Reading in DynamoDB [cite: 25, 143]
        vitals_table.put_item(
            Item={
                'patient_id': patient_id,
                'timestamp': timestamp,
                'hr': hr,
                'spo2': spo2,
                'bp_sys': bp_sys,
                'status': risk_status
            }
        )

        # Step 3: Trigger SNS Alert if Critical [cite: 26, 207]
        if risk_status == "critical":
            message = (
                f"🚨 [ALERT] Patient {patient_id} - CRITICAL\n"
                f"Anomaly detected at {timestamp}\n"
                f"Vitals: HR={hr}, SpO2={spo2}, BP={bp_sys}\n"
                f"Risk Level: {risk_status.upper()}"
            )
            
            # Record alert in DynamoDB for history
            alerts_table.put_item(
                Item={
                    'patient_id': patient_id,
                    'timestamp': timestamp,
                    'alert_msg': message
                }
            )

            # Send instant notification [cite: 242, 245]
            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Message=message,
                Subject=f"CRITICAL HEALTH ALERT: Patient {patient_id}"
            )

    return {
        'statusCode': 200,
        'body': json.dumps('Data processed and analyzed successfully.')
    }
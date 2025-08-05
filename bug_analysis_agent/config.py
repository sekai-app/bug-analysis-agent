"""
Configuration module for Bug Analysis Agent
"""

import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration settings for the bug analysis agent"""
    
    # OpenAI Configuration
    OPENAI_API_KEY: Optional[str] = os.getenv('OPENAI_API_KEY')
    GPT_MODEL: str = os.getenv('GPT_MODEL', 'gpt-4o')
    
    # AWS Configuration
    AWS_REGION: str = os.getenv('AWS_REGION', 'us-east-1')
    AWS_ACCESS_KEY_ID: Optional[str] = os.getenv('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY: Optional[str] = os.getenv('AWS_SECRET_ACCESS_KEY')
    CLOUDWATCH_LOG_GROUP: Optional[str] = os.getenv('CLOUDWATCH_LOG_GROUP')
    
    # S3 Configuration
    S3_BUCKET_NAME: str = os.getenv('S3_BUCKET_NAME')
    S3_ENABLED: bool = os.getenv('S3_ENABLED', 'true').lower() == 'true'
    
    # Webhook Configuration
    WEBHOOK_URL: Optional[str] = os.getenv('WEBHOOK_URL')
    WEBHOOK_TIMEOUT: int = int(os.getenv('WEBHOOK_TIMEOUT', '30'))
    WEBHOOK_RETRIES: int = int(os.getenv('WEBHOOK_RETRIES', '3'))
    WEBHOOK_ENABLED: bool = os.getenv('WEBHOOK_ENABLED', 'false').lower() == 'true'
    
    # Analysis Configuration
    DEFAULT_CONTEXT_LINES: int = int(os.getenv('DEFAULT_CONTEXT_LINES', '10'))
    DEFAULT_TIME_WINDOW_MINUTES: int = int(os.getenv('DEFAULT_TIME_WINDOW_MINUTES', '120'))  # 24 hours
    LOG_DOWNLOAD_TIMEOUT: int = int(os.getenv('LOG_DOWNLOAD_TIMEOUT', '30'))
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    
    @classmethod
    def is_openai_configured(cls) -> bool:
        """Check if OpenAI is properly configured"""
        return cls.OPENAI_API_KEY is not None
    
    @classmethod
    def is_aws_configured(cls) -> bool:
        """Check if AWS is properly configured"""
        return (
            cls.AWS_ACCESS_KEY_ID is not None and 
            cls.AWS_SECRET_ACCESS_KEY is not None
        ) or (
            # Check if using IAM roles or instance profile
            os.path.exists(os.path.expanduser('~/.aws/credentials')) or
            os.getenv('AWS_CONTAINER_CREDENTIALS_RELATIVE_URI') or
            os.getenv('AWS_EC2_METADATA_DISABLED') == 'true'
        )
    
    @classmethod
    def is_s3_configured(cls) -> bool:
        """Check if S3 is properly configured"""
        return cls.is_aws_configured() and cls.S3_ENABLED and cls.S3_BUCKET_NAME
    
    @classmethod
    def is_webhook_configured(cls) -> bool:
        """Check if webhook is properly configured"""
        return cls.WEBHOOK_ENABLED and cls.WEBHOOK_URL is not None
    
    @classmethod
    def get_summary(cls) -> dict:
        """Get configuration summary for debugging"""
        return {
            'openai_configured': cls.is_openai_configured(),
            'aws_configured': cls.is_aws_configured(),
            'webhook_configured': cls.is_webhook_configured(),
            'gpt_model': cls.GPT_MODEL,
            'aws_region': cls.AWS_REGION,
            'cloudwatch_log_group': cls.CLOUDWATCH_LOG_GROUP,
            'webhook_enabled': cls.WEBHOOK_ENABLED,
            'context_lines': cls.DEFAULT_CONTEXT_LINES,
            'time_window_minutes': cls.DEFAULT_TIME_WINDOW_MINUTES,
            'log_level': cls.LOG_LEVEL
        } 
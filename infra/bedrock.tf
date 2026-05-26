resource "aws_opensearchserverless_security_policy" "kb_encryption" {
  count = var.create_opensearch_collection ? 1 : 0

  name        = "${local.name_prefix}-kb-encryption"
  type        = "encryption"
  description = "Encryption policy for ${local.name_prefix} Bedrock knowledge base collection"
  policy = jsonencode({
    Rules = [{
      ResourceType = "collection"
      Resource     = ["collection/${local.name_prefix}-kb-collection"]
    }]
    AWSOwnedKey = true
  })
}

resource "aws_opensearchserverless_security_policy" "kb_network" {
  count = var.create_opensearch_collection ? 1 : 0

  name        = "${local.name_prefix}-kb-network"
  type        = "network"
  description = "Network policy for ${local.name_prefix} Bedrock knowledge base collection"
  policy = jsonencode([{
    Rules = [
      {
        ResourceType = "collection"
        Resource     = ["collection/${local.name_prefix}-kb-collection"]
      },
      {
        ResourceType = "dashboard"
        Resource     = ["collection/${local.name_prefix}-kb-collection"]
      },
    ]
    AllowFromPublic = true
  }])
}

resource "aws_opensearchserverless_collection" "kb" {
  count = var.create_opensearch_collection ? 1 : 0

  name        = "${local.name_prefix}-kb-collection"
  type        = "VECTORSEARCH"
  description = "${local.name_prefix} knowledge base vector store"

  depends_on = [
    aws_opensearchserverless_security_policy.kb_encryption,
    aws_opensearchserverless_security_policy.kb_network,
  ]
}

resource "aws_iam_role" "bedrock_kb" {
  count = var.create_opensearch_collection ? 1 : 0

  name = "AmazonBedrockExecutionRoleForKnowledgeBase_${local.name_prefix}"
  path = "/service-role/"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "AmazonBedrockKnowledgeBaseTrustPolicy"
      Effect = "Allow"
      Principal = {
        Service = "bedrock.amazonaws.com"
      }
      Action = "sts:AssumeRole"
      Condition = {
        StringEquals = {
          "aws:SourceAccount" = local.account_id
        }
        ArnLike = {
          "aws:SourceArn" = "arn:${local.partition}:bedrock:${local.region}:${local.account_id}:knowledge-base/*"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "bedrock_kb_s3" {
  count = var.create_opensearch_collection ? 1 : 0

  name = "S3Access"
  role = aws_iam_role.bedrock_kb[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:GetObject",
        "s3:ListBucket",
      ]
      Resource = [
        aws_s3_bucket.multimedia_kb.arn,
        "${aws_s3_bucket.multimedia_kb.arn}/*",
        aws_s3_bucket.kb_source.arn,
        "${aws_s3_bucket.kb_source.arn}/*",
      ]
    }]
  })
}

resource "aws_iam_role_policy" "bedrock_kb_opensearch" {
  count = var.create_opensearch_collection ? 1 : 0

  name = "OpenSearchAccess"
  role = aws_iam_role.bedrock_kb[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["aoss:APIAccessAll"]
      Resource = aws_opensearchserverless_collection.kb[0].arn
    }]
  })
}

resource "aws_iam_role_policy" "bedrock_kb_model" {
  count = var.create_opensearch_collection ? 1 : 0

  name = "BedrockModelAccess"
  role = aws_iam_role.bedrock_kb[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "bedrock:InvokeModel",
        "bedrock:GetInferenceProfile",
      ]
      Resource = "*"
    }]
  })
}

resource "aws_opensearchserverless_access_policy" "kb_data" {
  count = var.create_opensearch_collection ? 1 : 0

  name        = "${local.name_prefix}-kb-data"
  type        = "data"
  description = "Data access policy for ${local.name_prefix} Bedrock knowledge base collection"
  policy = jsonencode([{
    Rules = [
      {
        ResourceType = "collection"
        Resource     = ["collection/${local.name_prefix}-kb-collection"]
        Permission   = ["aoss:*"]
      },
      {
        ResourceType = "index"
        Resource     = ["index/${local.name_prefix}-kb-collection/*"]
        Permission   = ["aoss:*"]
      },
    ]
    Principal = [aws_iam_role.bedrock_kb[0].arn]
  }])
}

resource "aws_bedrockagent_knowledge_base" "main" {
  count = var.create_opensearch_collection ? 1 : 0

  name        = "${local.name_prefix}-kb"
  description = "${local.name_prefix}-kb"
  role_arn    = aws_iam_role.bedrock_kb[0].arn

  knowledge_base_configuration {
    type = "VECTOR"

    vector_knowledge_base_configuration {
      embedding_model_arn = "arn:${local.partition}:bedrock:${local.region}::foundation-model/cohere.embed-multilingual-v3"

      embedding_model_configuration {
        bedrock_embedding_model_configuration {
          embedding_data_type = "FLOAT32"
        }
      }

      supplemental_data_storage_configuration {
        storage_location {
          type = "S3"

          s3_location {
            uri = "s3://${aws_s3_bucket.kb_source.id}"
          }
        }
      }
    }
  }

  storage_configuration {
    type = "OPENSEARCH_SERVERLESS"

    opensearch_serverless_configuration {
      collection_arn    = aws_opensearchserverless_collection.kb[0].arn
      vector_index_name = "bedrock-knowledge-base-default-index"

      field_mapping {
        text_field     = "AMAZON_BEDROCK_TEXT"
        metadata_field = "AMAZON_BEDROCK_METADATA"
        vector_field   = "bedrock-knowledge-base-default-vector"
      }
    }
  }

  depends_on = [
    aws_iam_role_policy.bedrock_kb_s3,
    aws_iam_role_policy.bedrock_kb_opensearch,
    aws_iam_role_policy.bedrock_kb_model,
    aws_opensearchserverless_access_policy.kb_data,
  ]
}

resource "aws_bedrockagent_data_source" "main" {
  count = var.create_opensearch_collection ? 1 : 0

  knowledge_base_id    = aws_bedrockagent_knowledge_base.main[0].id
  name                 = "${local.name_prefix}-data-source"
  data_deletion_policy = "DELETE"

  data_source_configuration {
    type = "S3"

    s3_configuration {
      bucket_arn         = aws_s3_bucket.multimedia_kb.arn
      inclusion_prefixes = ["rag-documents/"]
    }
  }

  vector_ingestion_configuration {
    parsing_configuration {
      parsing_strategy = "BEDROCK_FOUNDATION_MODEL"

      bedrock_foundation_model_configuration {
        model_arn        = "arn:${local.partition}:bedrock:${local.region}:${local.account_id}:inference-profile/us.anthropic.claude-sonnet-4-5-20250929-v1:0"
        parsing_modality = "MULTIMODAL"
      }
    }
  }
}

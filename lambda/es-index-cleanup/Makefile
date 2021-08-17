.PHONY: build upload deploy clean

SRC_DIR		= src
DEPLOY_DIR      ?= $(PWD)
ARTIFACT        ?= es_cleanup_unsigned.zip

S3_KEY		?= $(ARTIFACT)

STACK_NAME	?= ElasticsearchIndexCleanup
INDEX_PREFIX	?= logstash-
INDEX_COUNT	?= 30

PARAMETERS	 = [
PARAMETERS	+= {"ParameterKey": "SourceBucket", "ParameterValue": "$(S3_BUCKET)"},
PARAMETERS	+= {"ParameterKey": "SourceKey", "ParameterValue": "$(S3_KEY)"},
PARAMETERS	+= {"ParameterKey": "ElasticsearchHostname", "ParameterValue": "$(ES_HOSTNAME)"},
PARAMETERS	+= {"ParameterKey": "IndexPrefix", "ParameterValue": "$(INDEX_PREFIX)"},
PARAMETERS	+= {"ParameterKey": "IndexCount", "ParameterValue": "$(INDEX_COUNT)"}
PARAMETERS	+= ]

build: 
	cd $(SRC_DIR) ; zip -r $(DEPLOY_DIR)/$(ARTIFACT) . -x '*.pyc'

upload: build
	aws s3 cp $(DEPLOY_DIR)/$(ARTIFACT) s3://$(S3_BUCKET)/$(S3_KEY)

deploy: upload
	aws cloudformation create-stack \
		--stack-name $(STACK_NAME) \
		--template-body file://cloudformation.yml \
		--capabilities CAPABILITY_NAMED_IAM \
		--parameters '$(PARAMETERS)'

clean:
	rm -rf $(ARTIFACT)
	rm -rf __pycache__

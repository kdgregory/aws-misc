.PHONY: default init build upload deploy clean

SRC_DIR		= src
BUILD_DIR	?= build
DEPLOY_DIR      ?= $(PWD)
ARTIFACT        ?= elb-to-es.zip

S3_KEY		?= $(ARTIFACT)

STACK_NAME	?= ELB-Elasticsearch-Upload
INDEX_PREFIX	?= elb-

PARAMETERS	 = [
PARAMETERS	+= {"ParameterKey": "LambdaName", "ParameterValue": "$(STACK_NAME)"},
PARAMETERS	+= {"ParameterKey": "SourceBucket", "ParameterValue": "$(S3_BUCKET)"},
PARAMETERS	+= {"ParameterKey": "SourceKey", "ParameterValue": "$(S3_KEY)"},
PARAMETERS	+= {"ParameterKey": "LogsBucket", "ParameterValue": "$(LOGS_BUCKET)"},
PARAMETERS	+= {"ParameterKey": "LogsPrefix", "ParameterValue": "$(LOGS_PREFIX)"},
PARAMETERS	+= {"ParameterKey": "ElasticsearchHostname", "ParameterValue": "$(ES_HOSTNAME)"},
PARAMETERS	+= {"ParameterKey": "ElasticsearchArn", "ParameterValue": "$(ES_ARN)"}
PARAMETERS	+= ]

default: build

init:
	pip install -t $(BUILD_DIR) -r requirements.txt --upgrade

build: init
	cp src/*.py $(BUILD_DIR)
	cd $(BUILD_DIR) ; zip -r $(DEPLOY_DIR)/$(ARTIFACT) . -x '*.pyc'

upload: build
	aws s3 cp $(DEPLOY_DIR)/$(ARTIFACT) s3://$(S3_BUCKET)/$(S3_KEY)

deploy: upload
	aws cloudformation create-stack \
		--stack-name $(STACK_NAME) \
		--template-body file://cloudformation.yml \
		--capabilities CAPABILITY_NAMED_IAM \
		--parameters '$(PARAMETERS)'

clean:
	rm -rf $(BUILD_DIR)
	rm -rf $(ARTIFACT)
	rm -rf __pycache__

.PHONY: build init upload deploy clean

BUILD_DIR	?= build
DEPLOY_DIR      ?= $(PWD)
ARTIFACT        ?= lambda.zip

build: init
	cp src/*.py $(BUILD_DIR)
	cd $(BUILD_DIR) ; zip -r $(DEPLOY_DIR)/$(ARTIFACT) . -x '*.pyc'

init:
	pip install -t $(BUILD_DIR) -r requirements.txt --upgrade

upload: build
	aws s3 cp $(DEPLOY_DIR)/$(ARTIFACT) s3://$(S3_BUCKET)/$(S3_KEY)

deploy: upload
	aws lambda update-function-code --function-name $(LAMBDA_NAME) --s3-bucket $(S3_BUCKET) --s3-key $(S3_KEY)

clean:
	rm -rf $(BUILD_DIR)
	rm -rf $(ARTIFACT)
	rm -rf __pycache__

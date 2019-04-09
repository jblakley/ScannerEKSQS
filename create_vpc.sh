DEFAULTVPC=eks-vpc
test -z "$VPC_STACK_NAME" && read -p "Enter the VPC_STACK_NAME [$DEFAULTVPC]: " VPC_STACK_NAME
test -z "$VPC_STACK_NAME" && VPC_STACK_NAME=$DEFAULTVPC

### 1. Create a VPC (virtual private cloud) to launch the cluster into
aws cloudformation describe-stacks --stack-name $VPC_STACK_NAME
VPC_EXISTS=$?
if [ $VPC_EXISTS -ne 0 ]; then
    aws cloudformation create-stack --stack-name $VPC_STACK_NAME \
        --template-body https://amazon-eks.s3-us-west-2.amazonaws.com/1.10.3/2018-06-05/amazon-eks-vpc-sample.yaml
fi

# Wait for stack to create
aws cloudformation wait stack-create-complete --stack-name $VPC_STACK_NAME
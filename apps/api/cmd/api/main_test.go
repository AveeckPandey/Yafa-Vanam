package main

import "testing"

func TestOrderConfirmationAWSRegion(t *testing.T) {
	t.Setenv("AWS_REGION", "")
	t.Setenv("AWS_DEFAULT_REGION", "")
	t.Setenv("YAFA_STORAGE_REGION", "ap-south-1")
	if got := orderConfirmationAWSRegion(); got != "ap-south-1" {
		t.Fatalf("orderConfirmationAWSRegion() = %q, want ap-south-1", got)
	}

	t.Setenv("AWS_DEFAULT_REGION", "eu-west-1")
	if got := orderConfirmationAWSRegion(); got != "eu-west-1" {
		t.Fatalf("orderConfirmationAWSRegion() = %q, want eu-west-1", got)
	}

	t.Setenv("AWS_REGION", "us-east-1")
	if got := orderConfirmationAWSRegion(); got != "us-east-1" {
		t.Fatalf("orderConfirmationAWSRegion() = %q, want us-east-1", got)
	}
}

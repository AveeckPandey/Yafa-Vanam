package yafa

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/base64"
	"errors"
	"fmt"
	"image"
	"image/jpeg"
	_ "image/png"
	"strings"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/credentials"
	"github.com/aws/aws-sdk-go-v2/service/s3"
)

const maxSelfieBytes = 5 << 20

type StorageConfig struct{ Endpoint, Region, Bucket, AccessKeyID, SecretAccessKey string }
type Storage struct {
	bucket  string
	client  *s3.Client
	presign *s3.PresignClient
}

func NewStorage(ctx context.Context, value StorageConfig) (*Storage, error) {
	if strings.TrimSpace(value.Endpoint) == "" || strings.TrimSpace(value.Region) == "" || strings.TrimSpace(value.Bucket) == "" || strings.TrimSpace(value.AccessKeyID) == "" || strings.TrimSpace(value.SecretAccessKey) == "" {
		return nil, errors.New("incomplete private object storage configuration")
	}
	endpoint := strings.TrimRight(value.Endpoint, "/")
	awsConfig, err := config.LoadDefaultConfig(ctx, config.WithRegion(value.Region), config.WithCredentialsProvider(credentials.NewStaticCredentialsProvider(value.AccessKeyID, value.SecretAccessKey, "")), config.WithBaseEndpoint(endpoint))
	if err != nil {
		return nil, err
	}
	client := s3.NewFromConfig(awsConfig, func(options *s3.Options) { options.UsePathStyle = true })
	return &Storage{bucket: value.Bucket, client: client, presign: s3.NewPresignClient(client)}, nil
}

func (s *Storage) StoreSelfie(ctx context.Context, sessionID string, source []byte) (string, error) {
	clean, err := sanitizeImage(source)
	if err != nil {
		return "", err
	}
	randomPart := make([]byte, 18)
	if _, err = rand.Read(randomPart); err != nil {
		return "", err
	}
	key := fmt.Sprintf("yafa/selfies/%s/%s.jpg", sessionID, base64.RawURLEncoding.EncodeToString(randomPart))
	_, err = s.client.PutObject(ctx, &s3.PutObjectInput{Bucket: aws.String(s.bucket), Key: aws.String(key), Body: bytes.NewReader(clean), ContentType: aws.String("image/jpeg"), CacheControl: aws.String("no-store")})
	return key, err
}

func (s *Storage) SignedReadURL(ctx context.Context, key string) (string, error) {
	request, err := s.presign.PresignGetObject(ctx, &s3.GetObjectInput{Bucket: aws.String(s.bucket), Key: aws.String(key)}, s3.WithPresignExpires(5*time.Minute))
	if err != nil {
		return "", err
	}
	return request.URL, nil
}

func sanitizeImage(source []byte) ([]byte, error) {
	if len(source) == 0 || len(source) > maxSelfieBytes {
		return nil, errors.New("invalid image size")
	}
	if !(bytes.HasPrefix(source, []byte{0xff, 0xd8, 0xff}) || bytes.HasPrefix(source, []byte{0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a})) {
		return nil, errors.New("unsupported image format")
	}
	decoded, _, err := image.Decode(bytes.NewReader(source))
	if err != nil {
		return nil, errors.New("invalid image data")
	}
	bounds := decoded.Bounds()
	if bounds.Dx() < 64 || bounds.Dy() < 64 || bounds.Dx() > 4096 || bounds.Dy() > 4096 {
		return nil, errors.New("unsupported image dimensions")
	}
	var output bytes.Buffer
	if err = jpeg.Encode(&output, decoded, &jpeg.Options{Quality: 90}); err != nil {
		return nil, err
	}
	return output.Bytes(), nil
}

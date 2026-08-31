package commerce

import (
	"context"
	"errors"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
)

var ErrReviewNotEligible = errors.New("a paid purchase is required to review this product")
var ErrReviewAlreadyExists = errors.New("this purchased item has already been reviewed")
var ErrInvalidReview = errors.New("review rating, title, or body is invalid")

type ProductReview struct {
	ID                 string    `json:"id"`
	ProductID          string    `json:"product_id"`
	VariantID          string    `json:"variant_id,omitempty"`
	Rating             int       `json:"rating"`
	Title              string    `json:"title"`
	Body               string    `json:"body"`
	DisplayName        string    `json:"display_name"`
	IsVerifiedPurchase bool      `json:"is_verified_purchase"`
	CreatedAt          time.Time `json:"created_at"`
}

type ProductReviewList struct {
	Items         []ProductReview `json:"items"`
	ReviewCount   int             `json:"review_count"`
	AverageRating float64         `json:"average_rating"`
}

type CreateReviewInput struct {
	OrderItemID string `json:"order_item_id"`
	Rating      int    `json:"rating"`
	Title       string `json:"title"`
	Body        string `json:"body"`
}

type ReviewStore interface {
	ListApprovedReviews(productID string, limit, offset int) (ProductReviewList, error)
	CreateVerifiedReview(userID, productID string, input CreateReviewInput) (ProductReview, error)
}

func (store *PostgresStore) ListApprovedReviews(productID string, limit, offset int) (ProductReviewList, error) {
	if limit <= 0 || limit > 50 {
		limit = 20
	}
	if offset < 0 {
		offset = 0
	}
	ctx, cancel := store.ctx()
	defer cancel()
	result := ProductReviewList{Items: []ProductReview{}}
	if err := store.db.QueryRow(ctx,
		`SELECT COUNT(*)::int, COALESCE(AVG(rating)::float8, 0)
		 FROM product_reviews WHERE product_id=$1 AND status='APPROVED'`, productID).
		Scan(&result.ReviewCount, &result.AverageRating); err != nil {
		return result, err
	}
	rows, err := store.db.Query(ctx,
		`SELECT id::text, product_id, COALESCE(variant_id,''), rating, title, body,
		        display_name, is_verified_purchase, created_at
		 FROM product_reviews WHERE product_id=$1 AND status='APPROVED'
		 ORDER BY published_at DESC NULLS LAST, id DESC LIMIT $2 OFFSET $3`, productID, limit, offset)
	if err != nil {
		return result, err
	}
	defer rows.Close()
	for rows.Next() {
		var review ProductReview
		if err := rows.Scan(&review.ID, &review.ProductID, &review.VariantID, &review.Rating,
			&review.Title, &review.Body, &review.DisplayName, &review.IsVerifiedPurchase, &review.CreatedAt); err != nil {
			return result, err
		}
		result.Items = append(result.Items, review)
	}
	return result, rows.Err()
}

func (store *PostgresStore) CreateVerifiedReview(userID, productID string, input CreateReviewInput) (ProductReview, error) {
	input.Title = strings.TrimSpace(input.Title)
	input.Body = strings.TrimSpace(input.Body)
	if userID == "" || input.Rating < 1 || input.Rating > 5 || len(input.Title) < 1 || len(input.Title) > 120 || len(input.Body) < 10 || len(input.Body) > 3000 {
		return ProductReview{}, ErrInvalidReview
	}
	ctx, cancel := context.WithTimeout(context.Background(), postgresTimeout)
	defer cancel()
	tx, err := store.db.Begin(ctx)
	if err != nil {
		return ProductReview{}, err
	}
	defer tx.Rollback(ctx)
	var variantID, displayName string
	err = tx.QueryRow(ctx,
		`SELECT oi.variant_id, COALESCE(NULLIF(TRIM(u.name),''), 'Verified customer')
		 FROM order_items oi
		 JOIN orders o ON o.id=oi.order_id
		 JOIN users u ON u.id=o.user_id
		 WHERE oi.id::text=$1 AND o.user_id::text=$2 AND oi.product_id=$3
		   AND o.payment_status IN ('AUTHORIZED','CAPTURED')
		 FOR UPDATE OF oi`, input.OrderItemID, userID, productID).Scan(&variantID, &displayName)
	if errors.Is(err, pgx.ErrNoRows) {
		return ProductReview{}, ErrReviewNotEligible
	}
	if err != nil {
		return ProductReview{}, err
	}
	if fields := strings.Fields(displayName); len(fields) > 1 {
		displayName = fields[0] + " " + string([]rune(fields[len(fields)-1])[0]) + "."
	}
	var review ProductReview
	err = tx.QueryRow(ctx,
		`INSERT INTO product_reviews
		 (user_id, product_id, variant_id, order_item_id, rating, title, body, display_name, is_verified_purchase, status)
		 VALUES ($1::uuid, $2, $3, $4::uuid, $5, $6, $7, $8, TRUE, 'PENDING')
		 RETURNING id::text, product_id, COALESCE(variant_id,''), rating, title, body,
		           display_name, is_verified_purchase, created_at`,
		userID, productID, variantID, input.OrderItemID, input.Rating, input.Title, input.Body, displayName).
		Scan(&review.ID, &review.ProductID, &review.VariantID, &review.Rating, &review.Title,
			&review.Body, &review.DisplayName, &review.IsVerifiedPurchase, &review.CreatedAt)
	if isUniqueViolation(err) {
		return ProductReview{}, ErrReviewAlreadyExists
	}
	if err != nil {
		return ProductReview{}, err
	}
	if err := tx.Commit(ctx); err != nil {
		return ProductReview{}, err
	}
	return review, nil
}

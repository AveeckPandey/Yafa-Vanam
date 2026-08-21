package auth

import (
	"fmt"
	"net/smtp"
	"strconv"
	"strings"
)

// Mailer deliberately receives only a completed reset URL. The token is never
// persisted in plaintext and is not included in application logs.
type Mailer interface {
	SendPasswordReset(to, resetURL string) error
}

type SMTPMailer struct {
	host, port, username, password, from string
}

func NewSMTPMailer(host, port, username, password, from string) Mailer {
	if strings.TrimSpace(host) == "" || strings.TrimSpace(from) == "" {
		return nil
	}
	if _, err := strconv.Atoi(port); err != nil || port == "" {
		port = "587"
	}
	return &SMTPMailer{host: host, port: port, username: username, password: password, from: from}
}

func (m *SMTPMailer) SendPasswordReset(to, resetURL string) error {
	subject := "Reset your YAFA VANAM password"
	body := "We received a request to reset your YAFA VANAM password.\r\n\r\n" +
		"Set a new password using this secure, one-time link (valid for one hour):\r\n" + resetURL +
		"\r\n\r\nIf you did not request this, you can safely ignore this email."
	message := fmt.Sprintf("From: %s\r\nTo: %s\r\nSubject: %s\r\nMIME-Version: 1.0\r\nContent-Type: text/plain; charset=UTF-8\r\n\r\n%s", m.from, to, subject, body)
	address := m.host + ":" + m.port
	var auth smtp.Auth
	if m.username != "" {
		auth = smtp.PlainAuth("", m.username, m.password, m.host)
	}
	return smtp.SendMail(address, auth, m.from, []string{to}, []byte(message))
}

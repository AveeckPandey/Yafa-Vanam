"use client";

import { FormEvent, useState } from "react";

export default function ContactForm() {
  const [sent, setSent] = useState(false);
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSent(true);
  };

  return <form className="contact-form" onSubmit={submit} noValidate>
    <div><label htmlFor="contact-name">Name</label><input id="contact-name" name="name" autoComplete="name" required /></div>
    <div><label htmlFor="contact-email">Email</label><input id="contact-email" name="email" type="email" autoComplete="email" required /></div>
    <div><label htmlFor="contact-topic">How can we help?</label><select id="contact-topic" name="topic" defaultValue="order"><option value="order">Order and delivery</option><option value="product">Product guidance</option><option value="returns">Returns</option><option value="other">Something else</option></select></div>
    <div><label htmlFor="contact-message">Message</label><textarea id="contact-message" name="message" rows={5} required /></div>
    <button type="submit">Send message</button>
    {sent ? <p className="contact-form__confirmation" role="status">Thank you. Your message has been prepared for the care team. Connect this form to your support inbox before launch to receive submissions.</p> : null}
  </form>;
}

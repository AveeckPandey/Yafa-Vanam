package yafa

import "testing"

func TestValidAnswerAcceptsOnlyConfiguredQuizValues(t *testing.T) {
	if !validAnswer("foundation_finish", "dewy") {
		t.Fatal("expected configured answer to be accepted")
	}
	for _, test := range []struct{ step, answer string }{
		{"unknown_step", "dewy"}, {"foundation_finish", "glossy"}, {"foundation_finish", string(make([]byte, 65))},
	} {
		if validAnswer(test.step, test.answer) {
			t.Fatalf("unexpected accepted answer: %#v", test)
		}
	}
}

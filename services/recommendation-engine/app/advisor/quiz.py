from __future__ import annotations

from .catalogue import active_products
from .models import AdvisorSession, QuizOption, QuizStep


def _opts(values: list[tuple[str, str]]) -> list[QuizOption]:
    return [QuizOption(value=value, label=label) for value, label in values]


STEPS = {
    "goal": QuizStep(id="goal", prompt="What would you like help with today?", options=_opts([
        ("full_look", "Build a complete makeup look"), ("complexion", "Find my complexion match"),
        ("lips", "Find lip products"), ("eyes", "Find eye makeup"), ("cheeks", "Find cheek products"),
        ("outfit_match", "Match makeup to my outfit"), ("guide_me", "I'm not sure — guide me")])),
    "match_method": QuizStep(id="match_method", prompt="How would you like to find your complexion match?", options=_opts([
        ("selfie", "Analyze a selfie"), ("manual", "I'll choose my skin depth and undertone"),
        ("known_shade", "I already know my YAFA VANAM shade"), ("skip", "Skip complexion products")]), skippable=True),
    "selfie_upload": QuizStep(id="selfie_upload", prompt="Upload a clear selfie in natural daylight, without a beauty filter and with minimal or no foundation.", options=[], skippable=True),
    "outfit_upload": QuizStep(id="outfit_upload", prompt="Upload an outfit photo so YAFA can extract its colours. You can skip this and continue with your selected colour mood.", options=[], skippable=True),
    "depth": QuizStep(id="depth", prompt="Which depth looks closest to your skin?", options=_opts([
        ("fair", "Fair"), ("light", "Light"), ("light_medium", "Light-Medium"), ("medium", "Medium"),
        ("medium_tan", "Medium-Tan"), ("tan", "Tan"), ("deep", "Deep"), ("rich", "Rich"), ("unknown", "I'm not sure")])) ,
    "undertone": QuizStep(id="undertone", prompt="Which undertone sounds closest to you?", options=_opts([
        ("cool", "Cool"), ("neutral", "Neutral"), ("warm", "Warm"), ("olive", "Olive"), ("unknown", "I'm not sure")])) ,
    "skin_type": QuizStep(id="skin_type", prompt="How does your skin usually feel during the day?", options=_opts([
        ("dry", "Dry / tight"), ("normal", "Normal / balanced"), ("combination", "Combination"),
        ("oily", "Oily / shiny"), ("sensitive", "Sensitive / easily irritated"), ("unknown", "I'm not sure")])) ,
    "coverage": QuizStep(id="coverage", prompt="How much coverage would you like?", options=_opts([
        ("sheer", "Sheer"), ("light", "Light"), ("medium", "Medium"), ("full", "Full"), ("unknown", "I'm not sure")])) ,
    "finish": QuizStep(id="finish", prompt="What finish do you prefer?", options=_opts([
        ("natural", "Natural / skin-like"), ("radiant", "Radiant / glowing"), ("soft_matte", "Soft matte"),
        ("matte", "Matte"), ("unknown", "I'm not sure")])) ,
    "occasion": QuizStep(id="occasion", prompt="Where are you wearing this look?", options=_opts([
        ("everyday", "Everyday"), ("work_college", "Work / college"), ("date_dinner", "Date / dinner"),
        ("party_night", "Party / night out"), ("wedding", "Wedding / celebration"),
        ("special_photos", "Special event / photos"), ("none", "No specific occasion")])) ,
    "style": QuizStep(id="style", prompt="How would you like the finished look to feel?", options=_opts([
        ("barely_there", "Barely-there"), ("natural", "Natural"), ("soft_glam", "Soft glam"),
        ("glam", "Glam"), ("bold", "Bold / expressive")])) ,
    "colour_family": QuizStep(id="colour_family", prompt="What colour mood are you drawn to today?", options=_opts([
        ("nude", "Nude / neutral"), ("rose", "Rose / pink"), ("peach", "Peach / coral"),
        ("mauve", "Mauve / plum"), ("brown", "Brown / earthy"), ("red", "Red / berry"), ("surprise", "Surprise me")])) ,
    "lip_finish": QuizStep(id="lip_finish", prompt="What lip finish do you prefer?", options=_opts([
        ("velvet", "Velvet / matte"), ("satin", "Satin"), ("glossy", "Glossy"), ("lip_oil", "Lip oil"),
        ("stain", "Stain"), ("plumping", "Plumping gloss"), ("none", "No preference")])) ,
    "eye_look": QuizStep(id="eye_look", prompt="What kind of eye look do you want?", options=_opts([
        ("natural", "Natural definition"), ("soft_smoky", "Soft smoky"), ("glam", "Glam"),
        ("colourful", "Colourful"), ("graphic", "Graphic / bold"), ("unknown", "I'm not sure")])) ,
    "mascara_priority": QuizStep(id="mascara_priority", prompt="What matters most for your mascara?", options=_opts([
        ("volume", "Volume"), ("lift", "Lift"), ("tubing", "Easy-removal tubing"), ("none", "No preference")]), skippable=True),
}




def _undertone_step(session: AdvisorSession) -> QuizStep:
    depth = session.answers.get("depth")
    reference = next((p for p in active_products() if p.get("name") == "Silkveil Serum Foundation"), None)
    labels = {"cool": "Cool", "neutral": "Neutral", "warm": "Warm", "olive": "Olive"}
    seen: list[str] = []
    if reference and depth:
        for variant in reference.get("variants", []):
            shade = variant.get("shade") or {}
            undertone = shade.get("undertone")
            if shade.get("depth_family") == depth and undertone and undertone not in seen:
                seen.append(undertone)
    options = [QuizOption(value=u, label=labels.get(u, u.title())) for u in seen]
    options.append(QuizOption(value="unknown", label="I'm not sure"))
    return QuizStep(id="undertone", prompt="Which undertone sounds closest to you?", options=options)

def _known_shade_step() -> QuizStep:
    reference = next((p for p in active_products() if p.get("name") == "Silkveil Serum Foundation"), None)
    options: list[QuizOption] = []
    if reference:
        for variant in reference.get("variants", []):
            shade = variant.get("shade") or {}
            if shade.get("code") and shade.get("name"):
                options.append(QuizOption(value=shade["code"], label=f'{shade["code"]} — {shade["name"]}'))
    return QuizStep(id="known_shade", prompt="Which YAFA VANAM master shade do you already know?", options=options)

def _needs_complexion(session: AdvisorSession) -> bool:
    return session.profile.goal and session.profile.goal.value in {"full_look", "complexion", "outfit_match", "guide_me"}


def _needs_lips(session: AdvisorSession) -> bool:
    return session.profile.goal and session.profile.goal.value in {"full_look", "lips", "outfit_match", "guide_me"}


def _needs_eyes(session: AdvisorSession) -> bool:
    return session.profile.goal and session.profile.goal.value in {"full_look", "eyes", "outfit_match", "guide_me"}


def next_step(session: AdvisorSession) -> QuizStep | None:
    a = session.answers
    if "goal" not in a:
        return STEPS["goal"]
    if _needs_complexion(session) and "match_method" not in a:
        return STEPS["match_method"]
    if _needs_complexion(session) and a.get("match_method") == "manual":
        if "depth" not in a: return STEPS["depth"]
        if a.get("depth") != "unknown" and "undertone" not in a: return _undertone_step(session)
    if _needs_complexion(session) and a.get("match_method") == "known_shade" and "known_shade" not in a:
        return _known_shade_step()
    if _needs_complexion(session) and a.get("match_method") == "selfie" and "selfie_upload" not in a:
        return STEPS["selfie_upload"]
    if _needs_complexion(session) and a.get("match_method") != "skip":
        for key in ("skin_type", "coverage", "finish"):
            if key not in a: return STEPS[key]
    if session.profile.goal and session.profile.goal.value == "outfit_match" and "outfit_upload" not in a:
        return STEPS["outfit_upload"]
    for key in ("occasion", "style", "colour_family"):
        if key not in a: return STEPS[key]
    if _needs_lips(session) and "lip_finish" not in a:
        return STEPS["lip_finish"]
    if _needs_eyes(session) and "eye_look" not in a:
        return STEPS["eye_look"]
    if _needs_eyes(session) and "mascara_priority" not in a:
        return STEPS["mascara_priority"]
    return None

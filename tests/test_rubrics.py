"""CAT-06: rubric classification (app.services.rubrics)."""

from app.services import rubrics


def test_keyword_classifier_hits_expected_rubrics():
    cases = {
        "Тушь для ресниц The One Wonder Lash": "Макияж",
        "Шампунь для окрашенных волос": "Уход за волосами",
        "Туалетная вода Miss O": "Парфюмерия",
        "Серьги «Незабудка»": "Украшения",
        "Гель для душа «Молоко и мёд»": "Уход за телом",
        "Дезодорант-антиперспирант 24-часового действия": "Дезодоранты",
        "Подарочный набор Milk & Honey Gold": "Наборы",
        "Крем для рук питательный": "Уход за руками и ногами",
        "Ночной восстанавливающий крем NovAge": "Уход за лицом",
    }
    for name, expected in cases.items():
        assert rubrics.classify_rubric_by_name(name) == expected, name


def test_bare_shade_name_falls_back_to_makeup():
    assert rubrics.classify_rubric_by_name("Медовый") == "Макияж"
    assert rubrics.classify_rubric_by_name("Яркая фуксия") == "Макияж"


def test_unknown_name_is_other():
    assert rubrics.classify_rubric_by_name("Каталог № 01 2023") == "Прочее"


def test_every_rubric_result_is_in_the_closed_set():
    for name in ["Тушь", "Медовый", "zzz непонятно", "Шампунь"]:
        assert rubrics.classify_rubric_by_name(name) in rubrics.RUBRICS


def test_overrides_are_loaded_and_valid():
    assert rubrics.RUBRIC_OVERRIDES, "web-verified overrides must be bundled"
    for code, entry in rubrics.RUBRIC_OVERRIDES.items():
        assert entry["rubric"] in rubrics.RUBRICS, code


def test_web_override_wins_over_name_heuristic():
    # 25429 "Красное дерево" is a HAIR DYE shade — the bare-name heuristic would
    # mislabel it Макияж, but the by-code override fixes it to hair care.
    code, bad_name = "25429", "Красное дерево"
    assert code in rubrics.RUBRIC_OVERRIDES
    assert rubrics.classify_rubric_by_name(bad_name) == "Макияж"  # heuristic alone
    assert rubrics.resolve_rubric(code, bad_name) == "Уход за волосами"  # override wins


FULL = "Увлажняющая тональная основа the one aqua boost - фарфоровый"


def test_is_shade_tail_accepts_a_bare_shade_of_a_fuller_name():
    assert rubrics.is_shade_tail("Фарфоровый", FULL)
    assert rubrics.is_shade_tail("фарфоровый", FULL), "case-folded"
    assert rubrics.is_shade_tail("  Фарфоровый  ", FULL), "both sides stripped"
    # The en/em dashes the price lists also use.
    assert rubrics.is_shade_tail("Ваниль", "Тональная основа – ваниль")
    assert rubrics.is_shade_tail("Ваниль", "Тональная основа — ваниль")


def test_is_shade_tail_refuses_a_name_that_already_carries_a_product_type():
    """The 34473 case: a hand-written full name can never be selected."""
    hand_written = "Женская туалетная вода Sunkiss Garden объем 50 мл"
    assert not rubrics.is_shade_tail(hand_written, FULL)
    # The realistic collision: the price list offers ANOTHER spelling of a name
    # that already names the product. It is not the tail, so it is not touched.
    assert not rubrics.is_shade_tail(
        "Тональная основа фарфоровый", FULL
    ), "a name that already carries the type is never the tail after a dash"


def test_is_shade_tail_refuses_equal_shorter_dashless_and_empty():
    assert not rubrics.is_shade_tail(FULL, FULL), "equal names"
    assert not rubrics.is_shade_tail("Фарфоровый", "Фарфор"), "restored is shorter"
    assert not rubrics.is_shade_tail(
        "основа", "Тональная основа"
    ), "a tail with no dash separator is not a shade"
    assert not rubrics.is_shade_tail("", FULL)
    assert not rubrics.is_shade_tail("   ", FULL)
    assert not rubrics.is_shade_tail("Фарфоровый", "- фарфоровый"), "no type before the dash"


def test_resolve_name_uses_corrected_name_for_bad_names():
    corrected = rubrics.resolve_name("25429", "Красное дерево")
    assert "краск" in corrected.lower()  # got the real product type
    # a code with no override keeps its original name
    assert rubrics.resolve_name("__no_such_code__", "Мочалка") == "Мочалка"

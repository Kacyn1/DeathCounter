from deathcounter.detector import DeathDetector

HIGH, LOW, MID = 0.95, 0.10, 0.65


def feed(detector, clock, scores, step=0.1):
    deaths = 0
    for score in scores:
        clock.advance(step)
        deaths += detector.update(score)
    return deaths


def test_single_death_counts_once(clock, settings):
    detector = DeathDetector(settings, clock)
    # rozgrywka, 4 s ekranu śmierci, 10 s rozgrywki
    assert feed(detector, clock, [LOW] * 20 + [HIGH] * 40 + [LOW] * 100) == 1


def test_requires_consecutive_confirmations(clock, settings):
    detector = DeathDetector(settings, clock)
    flicker = [HIGH, HIGH, LOW] * 20
    assert feed(detector, clock, flicker) == 0


def test_two_deaths_count_twice(clock, settings):
    detector = DeathDetector(settings, clock)
    life = [LOW] * 150
    death = [HIGH] * 40
    assert feed(detector, clock, life + death + life + death + life) == 2


def test_message_returning_too_soon_is_not_new_death(clock, settings):
    detector = DeathDetector(settings, clock)
    # napis zanika na 1 s (poniżej rearm_seconds) i wraca – to wciąż ten sam ekran śmierci
    assert feed(detector, clock, [HIGH] * 20 + [LOW] * 10 + [HIGH] * 20) == 1


def test_cooldown_blocks_rearm(clock, settings):
    settings.cooldown_seconds = 8.0
    settings.rearm_seconds = 1.0
    detector = DeathDetector(settings, clock)
    # po 3 s napisu i 2 s przerwy minęło dopiero 5 s od śmierci < cooldown
    assert feed(detector, clock, [HIGH] * 30 + [LOW] * 20 + [HIGH] * 30) == 1


def test_hysteresis_band_does_not_rearm(clock, settings):
    detector = DeathDetector(settings, clock)
    # wynik w paśmie histerezy (0.60–0.70) nie jest ani trafieniem, ani nieobecnością
    assert feed(detector, clock, [HIGH] * 5 + [MID] * 200 + [HIGH] * 5) == 1


def test_interrupt_resets_confirmations(clock, settings):
    detector = DeathDetector(settings, clock)
    feed(detector, clock, [HIGH, HIGH])
    detector.interrupt()
    assert feed(detector, clock, [HIGH, HIGH]) == 0
    assert feed(detector, clock, [HIGH]) == 1

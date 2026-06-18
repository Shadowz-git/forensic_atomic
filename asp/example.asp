before(px_accumulates_cash_from_criminal_activity, buys_car).
before(px_identifies_suitable_asset, buys_car).
before(px_selects_vehicle, buys_car).
before(px_selects_vehicle,
       px_arranges_payment_in_cash_or_structured_deposits).
before(px_arranges_payment_in_cash_or_structured_deposits,
       px_takes_possession_of_car_and_title).
before(px_takes_possession_of_car_and_title,
       to_register_car_in_own_name).
before(to_register_car_in_own_name,
       px_may_sell_car_to_further_layer_funds).

before(px_accumulates_cash_from_criminal_activity, buys_car).
before(px_identifies_suitable_asset, buys_car).
before(px_selects_vehicle, buys_car).
before(px_selects_vehicle,
       px_arranges_payment_in_cash_or_structured_deposits).
before(px_arranges_payment_in_cash_or_structured_deposits,
       px_takes_possession_of_car_and_title).
before(px_takes_possession_of_car_and_title,
       to_register_car_in_own_name).
before(to_register_car_in_own_name,
       px_may_sell_car_to_further_layer_funds).

possible_plan_step(E) :- before(E, _).
possible_plan_step(E) :- before(_, E).
{ inferred(E) } :- possible_plan_step(E), not observed(E).
in_plan(E) :- observed(E).
in_plan(E) :- inferred(E).
:- in_plan(B), before(A,B), not observed(A), not inferred(A).
:~ inferred(E). [1@1,E]


observed(buys_car).
observed(px_arranges_payment_in_cash_or_structured_deposits).
observed(px_takes_possession_of_car_and_title).

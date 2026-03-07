//Removing the lock and the buttons.
/obj/item/gun/dropped(mob/living/user)
	if(istype(user))
		user.stop_aiming(src)
	. = ..()
	// APRIL FOOLS: float like a balloon
	if(isturf(loc))
		animate(src, pixel_y = 3, time = 12, easing = SINE_EASING|EASE_OUT, loop = -1, flags = ANIMATION_END_NOW)
		animate(pixel_y = 0, time = 12, easing = SINE_EASING|EASE_IN)

/obj/item/gun/equipped(mob/living/user, slot)
	if(istype(user) && (slot != slot_l_hand && slot != slot_r_hand))
		user.stop_aiming(src)
	// APRIL FOOLS: stop float animation on pickup
	animate(src, flags = ANIMATION_END_NOW)
	pixel_y = 0
	return ..()

//Compute how to fire.....
//Return 1 if a target was found, 0 otherwise.
/obj/item/gun/proc/PreFire(atom/A, mob/living/user, params)
	if(!user.aiming)
		user.aiming = new(user)
	user.face_atom(A)
	if(ismob(A) && user.aiming)
		user.aiming.aim_at(A, src)
		return 1
	return 0

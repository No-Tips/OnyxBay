// APRIL FOOLS BUILD: flashbang replaced with party popper.
// Same detonation radius and pin mechanics. Confetti, glitter, mild stun. No blinding or deafening.
/obj/item/grenade/flashbang
	name = "party popper"
	desc = "Pull the pin and celebrate! Security-grade festive incapacitation."
	icon_state = "flashbang"
	item_state = "flashbang"
	origin_tech = list(TECH_MATERIAL = 2, TECH_COMBAT = 1)
	arm_sound = 'sound/items/party_horn.ogg'
	var/banglet = 0

/obj/item/grenade/flashbang/detonate()
	..()
	var/turf/T = get_turf(src)
	if(!T)
		qdel(src)
		return

	// Confetti and glitter burst in radius
	for(var/turf/simulated/floor/F in range(4, T))
		if(prob(60))
			new /obj/effect/decal/cleanable/confetti(F)
		if(prob(30))
			new /obj/effect/decal/cleanable/glitter(F)
	new /obj/effect/decal/cleanable/confetti(T)
	new /obj/effect/decal/cleanable/glitter(T)

	playsound(T, 'sound/items/champagne_pop.ogg', 80, TRUE,  5)
	playsound(T, 'sound/items/sitcom_laugh.ogg',  60, FALSE, 5)

	// Mild stun for nearby mobs — no blindness, no deafness
	for(var/mob/living/carbon/C in range(3, T))
		if(C.stat == DEAD)
			continue
		var/dist = get_dist(C, T)
		var/stun = max(0, 4 - dist)
		if(stun > 0)
			bang(T, C, stun)

	qdel(src)

/obj/item/grenade/flashbang/proc/bang(turf/T, mob/living/carbon/M, stun)
	to_chat(M, SPAN("notice", "HONK! Confetti explodes around you!"))
	playsound(M.loc, 'sound/items/bikehorn.ogg', 50, TRUE, 10)
	M.Stun(stun)
	M.Weaken(stun)
	M.confused = max(M.confused, stun * 2)
	M.update_icons()

/obj/item/grenade/flashbang/instant/Initialize()
	. = ..()
	name = "arcane energy"
	icon_state = null
	item_state = null
	detonate()

/obj/item/grenade/flashbang/clusterbang//Created by Polymorph, fixed by Sieve
	desc = "Use of this weapon may constiute a war crime in your area, consult your local captain."
	name = "clusterbang"
	icon = 'icons/obj/grenade.dmi'
	icon_state = "clusterbang"

/obj/item/grenade/flashbang/clusterbang/detonate()
	var/cluster_loc = loc
	var/numspawned = rand(4,8)
	var/again = 0
	for(var/more = numspawned,more > 0,more--)
		if(prob(35))
			again++
			numspawned --

	for(,numspawned > 0, numspawned--)
		spawn(0)
			new /obj/item/grenade/flashbang/cluster(cluster_loc)//Launches flashbangs
			playsound(src.loc, 'sound/weapons/armbomb.ogg', 75, 1, -3)

	for(,again > 0, again--)
		spawn(0)
			new /obj/item/grenade/flashbang/clusterbang/segment(cluster_loc)//Creates a 'segment' that launches a few more flashbangs
			playsound(src.loc, 'sound/weapons/armbomb.ogg', 75, 1, -3)
	qdel(src)
	return

/obj/item/grenade/flashbang/clusterbang/segment
	desc = "A smaller segment of a clusterbang. Better run."
	name = "clusterbang segment"
	icon = 'icons/obj/grenade.dmi'
	icon_state = "clusterbang_segment"

/obj/item/grenade/flashbang/clusterbang/segment/New()//Segments should never exist except part of the clusterbang, since these immediately 'do their thing' and asplode
	icon_state = "clusterbang_segment_active"
	active = 1
	banglet = 1
	var/stepdist = rand(1,4)//How far to step
	var/temploc = loc//Saves the current location to know where to step away from
	walk_away(src,temploc,stepdist)//I must go, my people need me
	var/dettime = rand(15,60)
	spawn(dettime)
		detonate()
	..()

/obj/item/grenade/flashbang/clusterbang/segment/detonate()
	var/cluster_loc = loc
	var/numspawned = rand(4,8)
	for(var/more = numspawned,more > 0,more--)
		if(prob(35))
			numspawned --

	for(,numspawned > 0, numspawned--)
		spawn(0)
			new /obj/item/grenade/flashbang/cluster(cluster_loc)
			playsound(src.loc, 'sound/weapons/armbomb.ogg', 75, 1, -3)
	qdel(src)
	return

/obj/item/grenade/flashbang/cluster/New()//Same concept as the segments, so that all of the parts don't become reliant on the clusterbang
	spawn(0)
		icon_state = "flashbang_active"
		active = 1
		banglet = 1
		var/stepdist = rand(1,3)
		var/temploc = src.loc
		walk_away(src,temploc,stepdist)
		var/dettime = rand(15,60)
		spawn(dettime)
		detonate()
	..()

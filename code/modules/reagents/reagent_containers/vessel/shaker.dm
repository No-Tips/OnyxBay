/obj/item/reagent_containers/vessel/shaker
    name = "shaker"
    desc = "A metal shaker to mix drinks in."
    icon_state = "shaker"
    amount_per_transfer_from_this = 10
    possible_transfer_amounts = "5;10;15;25;30;60" //Professional bartender should be able to transfer as much as needed
    volume = 120
    center_of_mass = "x=17;y=10"
    lid_type = /datum/vessel_lid/cap
    override_lid_state = LID_CLOSED
    precise_measurement = TRUE

/obj/item/reagent_containers/vessel/shaker/verb/rename_drink()
    set name = "Rename Your Coctail"
    set category = "Object"
    set src in usr

    if(!volume)
        return

    var/new_name = input(usr, "What would you like to name your coctail?", "Rename Coctail") as text|null
    if(!new_name)
        return

    var/new_volume = reagents.total_volume
    var/coctail_base = reagents.get_master_reagent_type()
    var/coctail_color = reagents.get_color()
    reagents.clear_reagents()
    reagents.add_reagent(coctail_base, new_volume) // Yeah, actually we do not mix all reagents, just do not say that to players

    var/datum/reagent/coctail = reagents.get_master_reagent()
    coctail.name = new_name
    coctail.glass_name = new_name
    coctail.color = coctail_color

    to_chat(usr, SPAN("notice","You renamed your coctail to [new_name]."))

    var/new_desc = input(usr, "What would you like to describe your coctail?", "Describe Coctail") as text|null
    if(!new_desc)
        return
    coctail.glass_desc = new_desc

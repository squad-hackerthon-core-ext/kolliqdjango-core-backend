# apps/users/management/commands/seed_jobs_and_listings.py

import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

# ── Employer phones (from seed_employers.py) ──────────────────────────────────
EMPLOYER_PHONES = [
    '+2348051003001',  # Kunle Adebayo       — Adebayo Logistics Ltd
    '+2348051003002',  # Priscilla Okafor    — Prisco Events & Catering
    '+2348051003003',  # Babatunde Lawal     — Lawal Construction Works
    '+2347061003001',  # Amaka Okonkwo       — Amaka Cleaning Services
    '+2347061003002',  # Suleiman Haruna     — Haruna Properties
    '+2347061003003',  # Ngozi Eze-Williams  — EzeWilliams Staffing
]

# ── Trader phones (from seed_pilot.py) ────────────────────────────────────────
TRADER_PHONES = [
    '+2347041002001',  # Raliat Adeleke Suleiman  — Garki Market, Abuja
    '+2348031002006',  # Blessing Adetola Ajayi   — Tejuosho Market, Lagos
    '+2347041002003',  # Abdullahi Maliq Danjuma  — Singer Market, Kano
    '+2347041002004',  # Hadiza Halimat Abubakar  — Nyanya Market, Abuja
    '+2348031002010',  # Funmilayo Aderonke Adebisi— Alaba Market, Lagos
    '+2348031002011',  # Nneka Chioma Obi         — Ogbete Market, Enugu
    '+2347041002006',  # Salihu Isa Balarabe      — Kurmi Market, Kano
    '+2348031002013',  # Aisha Precious Mahmud    — Wuse II Market, Abuja
]

# ── Placeholder images from picsum (free, no auth needed) ────────────────────
# Each key maps to a list of URLs we'll rotate through per category
IMAGES = {
    'food':      [f'https://picsum.photos/seed/food{i}/600/400'      for i in range(1, 8)],
    'clothing':  [f'https://picsum.photos/seed/cloth{i}/600/400'     for i in range(1, 8)],
    'household': [f'https://picsum.photos/seed/house{i}/600/400'     for i in range(1, 8)],
    'farm':      [f'https://picsum.photos/seed/farm{i}/600/400'      for i in range(1, 8)],
    'building':  [f'https://picsum.photos/seed/build{i}/600/400'     for i in range(1, 8)],
    'other':     [f'https://picsum.photos/seed/market{i}/600/400'    for i in range(1, 8)],
}

# ── Job templates per skill ───────────────────────────────────────────────────
# (title, description, skill, workers_needed, pay, duration_hours, city, area)
JOB_TEMPLATES = [

    # ── Kunle — Adebayo Logistics (delivery heavy) ───────────────────────────
    ('Dispatch Rider Needed — Lekki to Island',
     'Looking for experienced dispatch rider to deliver parcels across Lagos Island. Must have a working bike.',
     'delivery', 2, 4500, 8.0, 'Lagos', 'Lekki'),
    ('Package Delivery — Victoria Island',
     'Daily delivery runs within Victoria Island. 15–20 stops per day. Bike provided.',
     'delivery', 1, 3800, 7.0, 'Lagos', 'Victoria Island'),
    ('Warehouse Loading Assistant',
     'Help load and unload delivery trucks at our Apapa depot. Heavy lifting involved.',
     'other', 3, 3000, 6.0, 'Lagos', 'Apapa'),
    ('Errand Runner — Surulere',
     'Pick up documents, make payments, and run errands within Surulere and environs.',
     'delivery', 1, 2500, 4.0, 'Lagos', 'Surulere'),
    ('Last-Mile Delivery Agent — Yaba',
     'Handle last-mile delivery for e-commerce orders in Yaba. Must be punctual.',
     'delivery', 2, 4000, 8.0, 'Lagos', 'Yaba'),
    ('Same-Day Courier — Ikeja',
     'Same-day courier service for small parcels within Ikeja and Maryland.',
     'delivery', 1, 3500, 6.0, 'Lagos', 'Ikeja'),
    ('Logistics Coordinator Assistant',
     'Assist in coordinating daily delivery schedules. Basic admin and phone communication required.',
     'other', 1, 5000, 8.0, 'Lagos', 'Victoria Island'),
    ('Delivery Driver — 3-Axle Truck',
     'Drive our 3-axle truck for inter-state deliveries. Valid driver\'s license required.',
     'delivery', 1, 12000, 10.0, 'Lagos', 'Apapa'),
    ('Sorting Room Assistant',
     'Sort and label packages in our sorting facility. Evening shift available.',
     'other', 4, 2800, 5.0, 'Lagos', 'Ikeja'),
    ('Motorbike Rider — Mainland Routes',
     'Daily runs on Mainland routes: Agege, Ogba, Ikeja. Must know roads well.',
     'delivery', 3, 3600, 7.0, 'Lagos', 'Agege'),
    ('Pickup & Drop Agent — Airport Road',
     'Pick up clients and items from MMIA and deliver to their destination.',
     'delivery', 1, 6000, 5.0, 'Lagos', 'Ikeja'),
    ('Dispatch Supervisor',
     'Supervise a team of 5 riders. Track deliveries and resolve issues in real time.',
     'other', 1, 8000, 8.0, 'Lagos', 'Victoria Island'),
    ('Delivery Helper — Festac',
     'Assist delivery driver unloading and carrying items to customer doors.',
     'delivery', 2, 2500, 6.0, 'Lagos', 'Festac'),
    ('Document Courier — Lagos Mainland',
     'Urgent delivery of legal and financial documents within Lagos Mainland.',
     'delivery', 1, 3000, 4.0, 'Lagos', 'Surulere'),
    ('Overnight Logistics Guard',
     'Guard our parcel warehouse overnight. Must be reliable and security-conscious.',
     'security', 1, 5500, 12.0, 'Lagos', 'Apapa'),

    # ── Priscilla — Prisco Events & Catering ─────────────────────────────────
    ('Event Waitstaff — Lekki Wedding',
     'Serve food and drinks at a wedding reception in Lekki. Uniform provided. Saturday only.',
     'other', 6, 4000, 8.0, 'Lagos', 'Lekki'),
    ('Cook — Jollof Rice Station',
     'Experienced cook needed to manage jollof rice station at a corporate event. Min 3 years exp.',
     'cooking', 2, 6000, 6.0, 'Lagos', 'Victoria Island'),
    ('Kitchen Assistant — Weekly Contract',
     'Assist head chef in food prep for weekly corporate catering. Mon–Fri.',
     'cooking', 2, 3500, 5.0, 'Lagos', 'Ikoyi'),
    ('Food Packer — Catering Company',
     'Pack and label food items for delivery to offices. Early morning shift.',
     'cooking', 3, 2800, 4.0, 'Lagos', 'Surulere'),
    ('Event Setup Crew',
     'Set up chairs, tables, canopies, and decorations for events. Physical work.',
     'other', 5, 3000, 5.0, 'Lagos', 'Ikeja'),
    ('Dishwasher — Event Kitchen',
     'Wash up after large catering events. Multiple events per week.',
     'cleaning', 2, 2500, 4.0, 'Lagos', 'Lekki'),
    ('Buffet Attendant',
     'Man buffet stations at corporate events and weddings. Smart appearance required.',
     'other', 4, 3500, 6.0, 'Lagos', 'Victoria Island'),
    ('Head Cook — Private Dinner Party',
     'Prepare a 3-course Nigerian/Continental menu for 30 guests. Ingredients provided.',
     'cooking', 1, 15000, 8.0, 'Lagos', 'Ikoyi'),
    ('Event Cleanup Crew',
     'Post-event cleanup including removing decorations, washing items, general tidying.',
     'cleaning', 4, 2500, 4.0, 'Lagos', 'Lekki'),
    ('Outdoor Barbecue Cook',
     'Man outdoor BBQ stations at a large birthday party. Experience with suya/grills needed.',
     'cooking', 2, 7000, 5.0, 'Lagos', 'Ajah'),

    # ── Babatunde — Lawal Construction Works ─────────────────────────────────
    ('Block Layer — 3-Bedroom Project',
     'Experienced block layer needed for new residential build in Lekki. 4-week contract.',
     'construction', 4, 8000, 9.0, 'Lagos', 'Lekki'),
    ('General Labour — Foundation Work',
     'Mix concrete, carry materials, and assist skilled workers. Site in Ikorodu.',
     'construction', 6, 3500, 8.0, 'Lagos', 'Ikorodu'),
    ('Tiler — Bathroom & Living Room',
     'Tile 3 bathrooms and living room floor. Materials and tools provided.',
     'construction', 2, 7500, 8.0, 'Lagos', 'Ajah'),
    ('Painter — Interior & Exterior',
     'Paint 4-bedroom duplex, interior and exterior. Must supply own brushes.',
     'construction', 3, 6000, 8.0, 'Lagos', 'Gbagada'),
    ('Plumber — New Build',
     'Install plumbing for new 5-bedroom property. Experience with PVC and copper pipes.',
     'construction', 2, 9000, 8.0, 'Lagos', 'Lekki Phase 1'),
    ('Electrician — Wiring & Fittings',
     'Wire and install fittings for new residential property. Must have COREN certificate.',
     'construction', 2, 10000, 8.0, 'Lagos', 'Victoria Island'),
    ('Site Supervisor',
     'Supervise daily construction activities for a residential project. 3-month contract.',
     'construction', 1, 25000, 8.0, 'Lagos', 'Lekki'),
    ('Scaffolding Erector',
     'Erect and dismantle scaffolding for a 5-storey commercial building.',
     'construction', 4, 5000, 8.0, 'Lagos', 'Lagos Island'),
    ('Welder — Iron Railing',
     'Fabricate and install iron railings for staircase and balconies.',
     'construction', 1, 12000, 8.0, 'Lagos', 'Gbagada'),
    ('Concrete Mixer Operator',
     'Operate concrete mixer for continuous pour. 2-day job. Machine provided.',
     'construction', 1, 6000, 10.0, 'Lagos', 'Ikorodu'),

    # ── Amaka — Amaka Cleaning Services ──────────────────────────────────────
    ('Office Deep Clean — Wuse II',
     'Deep clean a 10-office floor including toilets, kitchen, and reception. Abuja.',
     'cleaning', 3, 4000, 6.0, 'Abuja', 'Wuse II'),
    ('Post-Construction Cleanup — Maitama',
     'Remove dust, debris and clean all surfaces after renovation. House in Maitama.',
     'cleaning', 4, 5000, 8.0, 'Abuja', 'Maitama'),
    ('Residential Weekly Clean',
     'Weekly cleaning of a 4-bedroom home in Asokoro. Every Thursday.',
     'cleaning', 2, 3500, 5.0, 'Abuja', 'Asokoro'),
    ('School Cleaning Staff — Daily',
     'Clean classrooms, toilets, and corridors at a private school in Garki.',
     'cleaning', 3, 3000, 4.0, 'Abuja', 'Garki'),
    ('Car Wash Attendant',
     'Wash and detail cars at a busy car wash in Wuse. Per car or daily rate.',
     'cleaning', 2, 2500, 8.0, 'Abuja', 'Wuse'),
    ('Hotel Room Cleaner — Contract',
     'Clean and prepare hotel rooms at a 3-star hotel in Abuja. Immediate start.',
     'cleaning', 4, 4500, 8.0, 'Abuja', 'Central Business District'),
    ('Soakaway Cleaning Crew',
     'Clean and pump soakaway pit. Heavy PPE provided. 1-day job.',
     'cleaning', 2, 6000, 6.0, 'Abuja', 'Lugbe'),
    ('Window Cleaning — High-Rise',
     'Clean exterior windows of 6-storey building using ropes. Experience required.',
     'cleaning', 2, 8000, 8.0, 'Abuja', 'Wuse II'),

    # ── Suleiman — Haruna Properties ─────────────────────────────────────────
    ('Security Guard — Residential Estate',
     'Guard a gated estate in Maitama. 12-hour shifts. Previous security exp required.',
     'security', 2, 6000, 12.0, 'Abuja', 'Maitama'),
    ('Estate Groundskeeper',
     'Maintain lawns, hedges, and flower beds at a luxury estate. Daily Monday–Saturday.',
     'other', 1, 4000, 6.0, 'Abuja', 'Asokoro'),
    ('Property Caretaker — Wuse',
     'Live-in caretaker for a 6-unit apartment block. Manage minor repairs and collect rent.',
     'other', 1, 35000, 8.0, 'Abuja', 'Wuse'),
    ('AC Technician — Servicing',
     'Service and re-gas 12 air conditioning units across 3 properties.',
     'other', 1, 15000, 8.0, 'Abuja', 'Maitama'),
    ('Plumber — Emergency Repair',
     'Fix burst pipe and faulty water heater in residential apartment. Urgent.',
     'construction', 1, 8000, 4.0, 'Abuja', 'Garki'),
    ('Painting — Rental Property Refresh',
     'Repaint interior of a 3-bedroom flat before new tenants move in.',
     'construction', 2, 5000, 8.0, 'Abuja', 'Wuse II'),
    ('Gate Man — Office Complex',
     'Man entrance gate at a commercial complex in CBD. 6-day week.',
     'security', 1, 5000, 8.0, 'Abuja', 'Central Business District'),

    # ── Ngozi — EzeWilliams Staffing ─────────────────────────────────────────
    ('Market Sales Assistant — Tejuosho',
     'Assist trader in selling fabric and clothing at Tejuosho market. Honest and hardworking.',
     'market', 2, 3000, 8.0, 'Lagos', 'Tejuosho'),
    ('Shop Attendant — Alaba Market',
     'Attend electronics shop in Alaba. Must be able to explain product features to customers.',
     'market', 1, 3500, 8.0, 'Lagos', 'Alaba'),
    ('Market Porter — Mile 12',
     'Carry goods for traders from trucks to stalls at Mile 12 market.',
     'market', 4, 2500, 6.0, 'Lagos', 'Mile 12'),
    ('Store Keeper — FMCG Warehouse',
     'Manage incoming and outgoing stock in an FMCG warehouse. Excel experience a plus.',
     'market', 1, 6000, 8.0, 'Lagos', 'Ojota'),
    ('Receptionist — Estate Agency',
     'Answer calls, manage appointments and greet clients at an estate agency in Surulere.',
     'other', 1, 5500, 8.0, 'Lagos', 'Surulere'),
    ('Data Entry Clerk',
     'Enter customer records into spreadsheet. Laptop provided. 3-day job.',
     'other', 1, 4000, 6.0, 'Lagos', 'Ikeja'),
    ('Teaching Assistant — Primary School',
     'Support class teacher in a private primary school. Must have SSCE minimum.',
     'teaching', 1, 4500, 6.0, 'Lagos', 'Yaba'),
    ('Private Lesson Teacher — Mathematics',
     'Teach mathematics to 3 SS2 students after school. 3 days per week.',
     'teaching', 1, 8000, 2.0, 'Lagos', 'Gbagada'),
    ('English Tutor — Primary Level',
     'Tutor two primary school pupils in English Language. Weekday evenings.',
     'teaching', 1, 6000, 2.0, 'Lagos', 'Surulere'),
    ('Cashier — Supermarket',
     'Handle POS and cash transactions at a busy supermarket in Ikeja.',
     'market', 1, 4000, 8.0, 'Lagos', 'Ikeja'),
]

# ── Listing templates per trader ──────────────────────────────────────────────
# (seller_phone, title, description, category_slug, price, price_type,
#  condition, qty, unit, image_key, market_name, city, area)
LISTING_TEMPLATES = [

    # ── Raliat — Garki Market, Abuja ──────────────────────────────────────────
    ('+2347041002001', 'Fresh Tomatoes — Basket', 'Freshly harvested tomatoes from Jos. Per basket. Available daily.',
     'food-groceries', 3500, 'negotiable', 'na', 20, 'per basket', 'food', 'Garki Market', 'Abuja', 'Garki'),
    ('+2347041002001', 'Palm Oil — 25 Litre Jerry Can', 'Fresh red palm oil from Benue. Good colour and taste. No adulteration.',
     'food-groceries', 12000, 'fixed', 'na', 10, 'per 25L jerry can', 'food', 'Garki Market', 'Abuja', 'Garki'),
    ('+2347041002001', 'Onions — 50kg Bag', 'Sokoto onions, dry and firm. Per bag. Sold wholesale and retail.',
     'food-groceries', 8500, 'negotiable', 'na', 30, 'per 50kg bag', 'food', 'Garki Market', 'Abuja', 'Garki'),
    ('+2347041002001', 'Dried Pepper Mix — 1kg', 'Blend of tatashe, shombo and scotch bonnet. Sun-dried and clean.',
     'food-groceries', 1200, 'fixed', 'na', 50, 'per 1kg pack', 'food', 'Garki Market', 'Abuja', 'Garki'),
    ('+2347041002001', 'Groundnut Oil — 5 Litres', 'Pure groundnut oil, no preservatives. Good for frying and cooking.',
     'food-groceries', 5500, 'fixed', 'na', 15, 'per 5L', 'food', 'Garki Market', 'Abuja', 'Garki'),

    # ── Blessing — Tejuosho Market, Lagos ────────────────────────────────────
    ('+2348031002006', 'Ankara Fabric — 6 Yards', 'High-quality Ankara wax print. Various patterns. Per 6-yard piece.',
     'clothing-fabric', 4500, 'negotiable', 'new', 40, 'per 6 yards', 'clothing', 'Tejuosho Market', 'Lagos', 'Tejuosho'),
    ('+2348031002006', 'Lace Fabric — French Net', 'Beautiful French net lace. Assorted colours. 5 yards per piece.',
     'clothing-fabric', 18000, 'fixed', 'new', 15, 'per 5 yards', 'clothing', 'Tejuosho Market', 'Lagos', 'Tejuosho'),
    ('+2348031002006', 'Aso-Oke Set — Owambe Ready', 'Complete aso-oke set (gele, buba, wrapper). Yoruba traditional. Multiple colours.',
     'clothing-fabric', 25000, 'negotiable', 'new', 8, 'per set', 'clothing', 'Tejuosho Market', 'Lagos', 'Tejuosho'),
    ('+2348031002006', 'Adire Fabric — Tie & Dye', 'Hand-crafted adire fabric. Indigo and modern colours. Per yard.',
     'clothing-fabric', 2000, 'fixed', 'new', 60, 'per yard', 'clothing', 'Tejuosho Market', 'Lagos', 'Tejuosho'),
    ('+2348031002006', 'School Uniform Fabric — Per Yard', 'Plain polycotton fabric for school uniforms. Various institutional colours.',
     'clothing-fabric', 900, 'fixed', 'new', 100, 'per yard', 'clothing', 'Tejuosho Market', 'Lagos', 'Tejuosho'),

    # ── Abdullahi — Singer Market, Kano ──────────────────────────────────────
    ('+2347041002003', 'Kano Leather Sandals — Handmade', 'Genuine cow leather sandals, handmade in Kano. Sizes 38–46.',
     'clothing-fabric', 6500, 'negotiable', 'new', 20, 'per pair', 'other', 'Singer Market', 'Kano', 'Singer'),
    ('+2347041002003', 'Groundnut — 50kg Bag', 'Fresh shelled groundnut from Kano farms. Good for oil and snacking.',
     'farm-produce', 9000, 'negotiable', 'na', 25, 'per 50kg bag', 'farm', 'Singer Market', 'Kano', 'Singer'),
    ('+2347041002003', 'Dates (Dabino) — 1kg', 'Premium Ajwa and Medjool dates imported and sold locally. Per kg.',
     'food-groceries', 3500, 'fixed', 'na', 30, 'per kg', 'food', 'Singer Market', 'Kano', 'Singer'),
    ('+2347041002003', 'Tukunya (Clay Pot) — Large', 'Traditional Hausa clay cooking pot. Ideal for soups and stews.',
     'household-goods', 2500, 'fixed', 'new', 12, 'per piece', 'household', 'Singer Market', 'Kano', 'Singer'),
    ('+2347041002003', 'Kano Embroidered Cap (Fula)', 'Handmade embroidered Hausa cap. Various sizes and designs.',
     'clothing-fabric', 3000, 'negotiable', 'new', 25, 'per piece', 'clothing', 'Singer Market', 'Kano', 'Singer'),

    # ── Hadiza — Nyanya Market, Abuja ─────────────────────────────────────────
    ('+2347041002004', 'Fresh Vegetables Bundle', 'Bundle includes ugu, waterleaf, spinach, and scent leaf. Very fresh.',
     'food-groceries', 800, 'fixed', 'na', 40, 'per bundle', 'food', 'Nyanya Market', 'Abuja', 'Nyanya'),
    ('+2347041002004', 'Frozen Fish — Titus (Mackerel)', 'Frozen Titus fish. Per kg. Sold in full carton or per kg.',
     'food-groceries', 2200, 'negotiable', 'na', 20, 'per kg', 'food', 'Nyanya Market', 'Abuja', 'Nyanya'),
    ('+2347041002004', 'Ofada Rice — Local Brown', 'Unpolished local Ofada rice. Good for health-conscious buyers.',
     'food-groceries', 1800, 'fixed', 'na', 35, 'per kg', 'food', 'Nyanya Market', 'Abuja', 'Nyanya'),
    ('+2347041002004', 'Crayfish — 500g Pack', 'Dried and ground crayfish from the East. Good quality.',
     'food-groceries', 2500, 'fixed', 'na', 30, 'per 500g pack', 'food', 'Nyanya Market', 'Abuja', 'Nyanya'),
    ('+2347041002004', 'Egusi (Melon Seeds) — 1kg', 'Shelled and clean egusi. Ready for grinding. Per kg.',
     'food-groceries', 2800, 'negotiable', 'na', 25, 'per kg', 'food', 'Nyanya Market', 'Abuja', 'Nyanya'),

    # ── Funmilayo — Alaba Market, Lagos ──────────────────────────────────────
    ('+2348031002010', 'Used Laptop — Dell Inspiron 15', 'Dell Inspiron 15, Core i5, 8GB RAM, 256GB SSD. Excellent condition.',
     'electronics', 95000, 'negotiable', 'used_good', 1, 'per unit', 'other', 'Alaba Market', 'Lagos', 'Alaba'),
    ('+2348031002010', 'Phone Accessories Bundle', 'Bundle: screen protector, phone case, fast charger, earphones. Universal fit.',
     'electronics', 3500, 'fixed', 'new', 50, 'per bundle', 'other', 'Alaba Market', 'Lagos', 'Alaba'),
    ('+2348031002010', 'Bluetooth Speaker — JBL Clone', 'Good quality JBL-style portable speaker. Waterproof. USB & Bluetooth.',
     'electronics', 8000, 'negotiable', 'new', 15, 'per unit', 'other', 'Alaba Market', 'Lagos', 'Alaba'),
    ('+2348031002010', 'Electric Iron — Steam', 'Heavy-duty steam iron for home and commercial use. 2-year warranty.',
     'household-goods', 5500, 'fixed', 'new', 20, 'per unit', 'household', 'Alaba Market', 'Lagos', 'Alaba'),
    ('+2348031002010', 'Standing Fan — 18 Inch', '18-inch standing fan with 3 speed settings. Energy saving motor.',
     'household-goods', 18000, 'negotiable', 'new', 10, 'per unit', 'household', 'Alaba Market', 'Lagos', 'Alaba'),

    # ── Nneka — Ogbete Market, Enugu ─────────────────────────────────────────
    ('+2348031002011', 'Uziza Leaves — Fresh', 'Fresh uziza leaves for ofe onugbu and pepper soup. Daily supply.',
     'farm-produce', 300, 'fixed', 'na', 60, 'per bunch', 'farm', 'Ogbete Market', 'Enugu', 'Ogbete'),
    ('+2348031002011', 'Ukwa (Breadfruit) — Per Cup', 'Freshly harvested breadfruit. Traditional Igbo delicacy.',
     'farm-produce', 500, 'fixed', 'na', 40, 'per cup', 'farm', 'Ogbete Market', 'Enugu', 'Ogbete'),
    ('+2348031002011', 'Palm Kernel — 1kg', 'Cracked palm kernel from the village. Good for palm kernel oil.',
     'farm-produce', 1200, 'negotiable', 'na', 30, 'per kg', 'farm', 'Ogbete Market', 'Enugu', 'Ogbete'),
    ('+2348031002011', 'Ofe Onugbu Ingredients Kit', 'Complete kit for bitter leaf soup: ofo, cocoyam, stockfish, crayfish.',
     'food-groceries', 4500, 'fixed', 'na', 20, 'per kit', 'food', 'Ogbete Market', 'Enugu', 'Ogbete'),
    ('+2348031002011', 'Nkwobi Spice Pack', 'Ready-mixed spices for nkwobi. Includes utazi, ehuru, and ugba.',
     'food-groceries', 1500, 'fixed', 'na', 35, 'per pack', 'food', 'Ogbete Market', 'Enugu', 'Ogbete'),

    # ── Salihu — Kurmi Market, Kano ──────────────────────────────────────────
    ('+2347041002006', 'Wholesale Rice — 50kg Bag', 'Ofada and local long grain rice. Sold in bags. Good wholesale price.',
     'food-groceries', 32000, 'negotiable', 'na', 40, 'per 50kg bag', 'food', 'Kurmi Market', 'Kano', 'Kurmi'),
    ('+2347041002006', 'Cow Hide (Ponmo) — Per Kg', 'Cleaned and processed cow hide. Soft texture. Sold per kg.',
     'food-groceries', 2800, 'fixed', 'na', 25, 'per kg', 'food', 'Kurmi Market', 'Kano', 'Kurmi'),
    ('+2347041002006', 'Leather Belt — Handcrafted', 'Genuine leather belt with brass buckle. Sizes 28–42 inches.',
     'clothing-fabric', 4000, 'negotiable', 'new', 18, 'per piece', 'other', 'Kurmi Market', 'Kano', 'Kurmi'),
    ('+2347041002006', 'Woven Raffia Mat — Large', 'Hand-woven raffia floor mat. Good for prayer and home use.',
     'household-goods', 2200, 'fixed', 'new', 22, 'per piece', 'household', 'Kurmi Market', 'Kano', 'Kurmi'),
    ('+2347041002006', 'Neem Powder (Dogonyaro) — 500g', 'Dried and ground neem leaves. Traditional medicine and insect repellent.',
     'other', 800, 'fixed', 'na', 50, 'per 500g pack', 'other', 'Kurmi Market', 'Kano', 'Kurmi'),

    # ── Aisha — Wuse II Market, Abuja ─────────────────────────────────────────
    ('+2348031002013', 'Frozen Chicken — Full Bird', 'Whole frozen broiler chicken. Cleaned and bagged. Per kg pricing.',
     'food-groceries', 2500, 'fixed', 'na', 30, 'per kg', 'food', 'Wuse II Market', 'Abuja', 'Wuse II'),
    ('+2348031002013', 'Seasoning & Spice Bundle', 'Bundle: Maggi, Knorr, curry, thyme, bay leaves. Wholesale pricing.',
     'food-groceries', 3200, 'fixed', 'na', 25, 'per bundle', 'food', 'Wuse II Market', 'Abuja', 'Wuse II'),
    ('+2348031002013', 'Cooking Gas Refill — 12.5kg', 'Refill for 12.5kg gas cylinder. Safe and certified refill point.',
     'household-goods', 12000, 'fixed', 'na', 20, 'per refill', 'household', 'Wuse II Market', 'Abuja', 'Wuse II'),
    ('+2348031002013', 'Plastic Storage Containers — Set of 6', 'Airtight plastic food containers. Microwave and freezer safe.',
     'household-goods', 4500, 'fixed', 'new', 15, 'per set of 6', 'household', 'Wuse II Market', 'Abuja', 'Wuse II'),
    ('+2348031002013', 'Semovita — 1kg Pack', 'Semovita flour. Multiple brands available. Per 1kg pack.',
     'food-groceries', 1100, 'fixed', 'na', 60, 'per 1kg pack', 'food', 'Wuse II Market', 'Abuja', 'Wuse II'),
]

LOCATION_MAP = {
    'Lagos': (Decimal('6.5244'), Decimal('3.3792')),
    'Kano':  (Decimal('12.0022'), Decimal('8.5920')),
    'Abuja': (Decimal('9.0579'), Decimal('7.4951')),
    'Enugu': (Decimal('6.4584'), Decimal('7.5464')),
}

STATUSES_WEIGHTED = ['open'] * 6 + ['filled'] * 2 + ['in_progress'] * 1 + ['completed'] * 1


class Command(BaseCommand):
    help = 'Seed 100 jobs (from employer accounts) and marketplace listings (from trader accounts)'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Delete existing seeded jobs and listings first')

    def handle(self, *args, **options):
        from apps.jobs.models import Job
        from apps.marketplace.models import Listing, ListingImage, Category

        if options['reset']:
            self.stdout.write(self.style.WARNING('Deleting existing jobs and listings...'))
            Job.objects.filter(employer__phone__in=EMPLOYER_PHONES).delete()
            Listing.objects.filter(seller__phone__in=TRADER_PHONES).delete()
            self.stdout.write('  ✅ Cleared\n')

        # ── JOBS ──────────────────────────────────────────────────────────────
        self.stdout.write('📋 Seeding jobs...\n')

        employers = {u.phone: u for u in User.objects.filter(phone__in=EMPLOYER_PHONES)}
        if not employers:
            self.stdout.write(self.style.ERROR(
                'No employer accounts found. Run seed_employers first.'
            ))
            return

        jobs_created = 0
        for i, (title, description, skill, workers_needed, pay,
                duration_hours, city, area) in enumerate(JOB_TEMPLATES):

            # Assign to employer deterministically (round-robin)
            employer_phone = EMPLOYER_PHONES[i % len(EMPLOYER_PHONES)]
            employer = employers.get(employer_phone)
            if not employer:
                continue

            lat, lng = LOCATION_MAP.get(city, (Decimal('6.5244'), Decimal('3.3792')))

            # Vary the status realistically
            job_status = random.choice(STATUSES_WEIGHTED)

            # Stagger created_at over last 60 days
            days_ago = random.randint(0, 60)
            created_at = timezone.now() - timedelta(days=days_ago)

            job = Job.objects.create(
                employer=employer,
                title=title,
                description=description,
                skill_required=skill,
                workers_needed=workers_needed,
                pay_per_worker=Decimal(str(pay)),
                duration_hours=Decimal(str(duration_hours)),
                location_area=area,
                location_city=city,
                location_lat=lat,
                location_lng=lng,
                status=job_status,
                source_channel=random.choice(['app', 'whatsapp']),
                escrow_funded=job_status in ('in_progress', 'completed'),
                start_time=timezone.now() + timedelta(days=random.randint(1, 14)),
            )

            # Manually set created_at since auto_now_add doesn't allow override
            Job.objects.filter(pk=job.pk).update(created_at=created_at)

            jobs_created += 1
            self.stdout.write(f'  ✅ [{job_status:<11}] {title[:55]}')

        self.stdout.write(self.style.SUCCESS(f'\n  {jobs_created} jobs created.\n'))

        # ── LISTINGS ──────────────────────────────────────────────────────────
        self.stdout.write('🛒 Seeding marketplace listings...\n')

        traders = {u.phone: u for u in User.objects.filter(phone__in=TRADER_PHONES)}
        if not traders:
            self.stdout.write(self.style.ERROR(
                'No trader accounts found. Run seed_pilot first.'
            ))
            return

        listings_created = 0
        for (seller_phone, title, description, category_slug, price, price_type,
             condition, qty, unit, image_key, market_name, city, area) in LISTING_TEMPLATES:

            seller = traders.get(seller_phone)
            if not seller:
                self.stdout.write(self.style.WARNING(f'  ⚠  Trader {seller_phone} not found, skipping'))
                continue

            category = Category.objects.filter(slug=category_slug).first()
            lat, lng = LOCATION_MAP.get(city, (Decimal('6.5244'), Decimal('3.3792')))

            days_ago = random.randint(0, 45)
            created_at = timezone.now() - timedelta(days=days_ago)

            listing = Listing.objects.create(
                seller=seller,
                category=category,
                title=title,
                description=description,
                price=Decimal(str(price)),
                price_type=price_type,
                condition=condition,
                quantity_available=qty,
                unit=unit,
                location_area=area,
                location_city=city,
                location_lat=lat,
                location_lng=lng,
                market_name=market_name,
                whatsapp_number=seller.phone,
                call_number=seller.phone,
                show_phone=True,
                status='active',
                views_count=random.randint(5, 120),
                enquiries_count=random.randint(0, 15),
                source_channel='app',
            )

            Listing.objects.filter(pk=listing.pk).update(created_at=created_at)

            # Add 2 images per listing from our placeholder pool
            image_pool = IMAGES.get(image_key, IMAGES['other'])
            for order, url in enumerate(random.sample(image_pool, min(2, len(image_pool)))):
                ListingImage.objects.create(
                    listing=listing,
                    image_url=url,
                    is_primary=(order == 0),
                    upload_order=order,
                )

            listings_created += 1
            self.stdout.write(f'  🛒 {title[:55]} — ₦{price:,}')

        self.stdout.write(self.style.SUCCESS(f'\n  {listings_created} listings created.\n'))

        self.stdout.write(self.style.SUCCESS(
            f'✅ Done. {jobs_created} jobs + {listings_created} listings seeded.\n\n'
            f'📋 Jobs breakdown:\n'
            f'  Kunle  (Logistics)   — 15 delivery/security jobs\n'
            f'  Priscilla (Events)   — 10 cooking/cleaning jobs\n'
            f'  Babatunde (Construct)— 10 construction jobs\n'
            f'  Amaka (Cleaning)     — 8  cleaning jobs\n'
            f'  Suleiman (Property)  — 7  security/maintenance jobs\n'
            f'  Ngozi (Staffing)     — 10 market/teaching/admin jobs\n\n'
            f'🛒 Listings breakdown:\n'
            f'  Raliat   — 5 food listings (Garki, Abuja)\n'
            f'  Blessing — 5 fabric/clothing (Tejuosho, Lagos)\n'
            f'  Abdullahi— 5 mixed (Singer, Kano)\n'
            f'  Hadiza   — 5 food listings (Nyanya, Abuja)\n'
            f'  Funmilayo— 5 electronics/household (Alaba, Lagos)\n'
            f'  Nneka    — 5 farm produce (Ogbete, Enugu)\n'
            f'  Salihu   — 5 mixed (Kurmi, Kano)\n'
            f'  Aisha    — 5 food/household (Wuse II, Abuja)\n'
        ))
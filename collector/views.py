# --- DJANGO SHORTCUTS & CORE IMPORTS ---
# render: Standard template rendering shortcut (unused here since we are returning API JSON responses).
from datetime import timedelta

from django.utils import timezone
from django.db.models import Sum

from django.shortcuts import render
# transaction: Used to bundle related database creations together so if one fails, everything rolls back.
from django.db import transaction
# get_user_model: Securely retrieves the active Custom User model configuration defined in your project settings.
from django.contrib.auth import get_user_model

# --- DJANGO REST FRAMEWORK (DRF) TOOLS ---
# api_view: Decorator that wraps functions into DRF API views, enabling them to safely receive explicit HTTP verbs (like POST).
# permission_classes: Restricts access to a specific endpoint based on whether the user satisfies predefined criteria.
from rest_framework.decorators import api_view, permission_classes
# IsAuthenticated: Security class requiring a valid authorization token in the request header to gain access.
# AllowAny: Security class that keeps endpoints completely public (useful for signup/register routes).
from rest_framework.permissions import IsAuthenticated, AllowAny
# Response: Core DRF object that serializes Python dictionaries seamlessly into standard JSON payloads returned to clients.
from rest_framework.response import Response

# --- CORE APP MODEL IMPORTS ---
# FarmerProfile, MilkCollection, PorterProfile: Your custom database tables tracking dairy operations, users, and collection records.
from collector.serializer import MilkCollectionSerializer, RecentCollectionSerializer
from cooperative.serializer import NoticeSerializer
from core.models import FarmerProfile, MilkCollection, Notice, PorterProfile

from rest_framework import generics


# Porters dashboard
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def PorterDashboard(request):
    # get the logged porter/user from the token
    try:
        porter=request.user.porter_profile
    except PorterProfile.DoesNotExist:
        return Response({"error":"Only porters can access this dashboard"})
    
    # time settings 
    today=timezone.now().date()
    week_start=today-timedelta(days=7)
    month_start=today.replace(day=1)

    # Todays collections
    today_collections=MilkCollection.objects.filter(porter=porter, collection_date=today)
    total_collection_today=today_collections.count()
    total_liters_today=today_collections.aggregate(total=Sum('liters'))["total"] or 0
    total_amount_today=today_collections.aggregate(total=Sum('total_amount'))["total"] or 0

    # weekly/monthly
    weekly_collections=MilkCollection.objects.filter(porter=porter, collection_date__gte=week_start)
    total_liters_week=weekly_collections.aggregate(total=Sum('liters'))["total"] or 0


    monthly_collections=MilkCollection.objects.filter(porter=porter, collection_date__gte=month_start)
    total_liters_month=monthly_collections.aggregate(total=Sum('liters'))["total"] or 0

    # current 5 collections
    last_collections=MilkCollection.objects.filter(porter=porter).order_by("created_at")[:5]

    # serialize the multiple milk collection record since last_collection is a queryset-multiple objects
    last_collections_list=RecentCollectionSerializer(
        last_collections,
        many=True # DRF serializers each collection individually-without it we treat it as a single object
    ).data #returns the serialized JSON-ready representation of the query

    response_data={
        'date':today,
        'assigned_farmers':porter.assigned_farmers.count(),
        'total_collections_today':total_collection_today,
        'total_liters_today':total_liters_today,
        'total_amount_today':total_amount_today,
        'total_liters_week':total_liters_week,
        'total_liters_month':total_liters_month,
        'last_collections':last_collections_list,
        'porter_name':f"{porter.first_name} {porter.last_name}",
        'route_name':porter.route_name,
        'employee_id':porter.employee_id
    }
    return Response(response_data)




# Initialize the Custom User model tracking instance
User = get_user_model()


# ==========================================
# 1. ADD MILK COLLECTION (PROTECTED VIEW)
# ==========================================
@api_view(['POST'])                             # Configures this endpoint to explicitly accept only incoming HTTP POST requests.
@permission_classes([IsAuthenticated])           # Secures the endpoint; requests must pass a valid 'Bearer <token>' inside the header.
def AddMilkCollection(request):
    """
    Records a new dairy collection transaction log.
    Bridges an authenticated Porter to a registered Farmer via their national identity record.
    """
    # request.data: Parses incoming JSON payload values into a readable Python dictionary map.
    data = request.data
    try:
        # 1. Extract the Porter identity by mapping the authenticated user straight to their OneToOne profile extension.
        # Throws an exception if the user logged in does not have a linked porter profile.
        porter = request.user.porter_profile
        
        # 2. Look up the targeted Farmer entity using the unique 'national_id' string sent in the JSON body.
        farmer = FarmerProfile.objects.get(national_id=data.get('national_id'))
        
        # 3. Create and commit the transaction record to the database table.
        collection = MilkCollection.objects.create(
            farmer=farmer,                 # Assigns the linked Farmer object instance.
            porter=porter,                 # Assigns the logged-in Porter object instance.
            liters=data.get('liters'),     # Captures volume metrics from the request data.
            session=data.get('session')    # Captures current scheduling session windows (e.g., "Morning", "Evening").
        )
        
        # Return structured success details indicating operational completion.
        return Response({
            "message": "Milk collection recorded successfully!",
            "collection_id": collection.id
        }, status=200)
        
    except FarmerProfile.DoesNotExist:
        # Custom Error Catch: Triggered if FarmerProfile.objects.get() finds no records matching the provided national identity.
        return Response({"error": "Farmer not Found"}, status=404)
        
    except Exception as e:
        # General Error Catch: Handles any other unexpected runtime issues (e.g., parsing errors, database row blocks).
        return Response({"error": str(e)}, status=400)


# ==========================================
# 2. PORTER REGISTRATION ENTRANCE (SHELL ENDPOINT)
# ==========================================
@api_view(['POST'])                             # Configures the endpoint for incoming data submissions via POST.
@permission_classes([AllowAny])                 # Opens the route to the public so new porters can sign up.
def RegisterPorter(request):
    """
    Placeholder endpoint ready for porter profile routing logic.
    """
    return Response({"message": "Porter endpoint setup ready"})


# ==========================================
# 3. FARMER REGISTRATION VIEW (ATOMIC TRANSACTION)
# ==========================================
@api_view(['POST'])                             # Restricts route interactions to incoming POST payloads.
@permission_classes([AllowAny])                 # Explicitly public endpoint allowing unauthorized anonymous registrations.
def RegisterFarmer(request):
    """
    Provisions a base user account and links a descriptive farmer profile entity synchronously.
    Uses context-managed transactions to prevent corrupt or partial user account generation.
    """
    # Extract complete set of identity, contact, and agricultural tracking credentials from JSON payload parameters.
    data = request.data
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    phone_number = data.get('phone_number')
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    national_id = data.get('national_id')
    farm_name = data.get('farm_name')

    try:
        # with transaction.atomic(): Wraps everything nested inside it into a single database block.
        # Safety net: If user creation passes but farmer_profile fails, it completely un-does (rolls back) the user creation.
        with transaction.atomic():
            # 1. Provision foundational system user credentials while auto-hashing raw password parameters.
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                phone_number=phone_number,
                role='farmer'               # Sets the specific custom internal tracking role identifier.
            )
            
            # 2. Initialize the matching tracking profile record explicitly tied back to the user object record row.
            farmer_profile = FarmerProfile.objects.create(
                user=user,                 # ForeignKey/OneToOne assignment mapping back to our user instance.
                national_id=national_id,
                first_name=first_name,
                last_name=last_name,
                location=farm_name         # Maps input farm name parameter straight into the model location attribute.
            )
            
        # Return success confirmation payload if BOTH components write to the database successfully.
        return Response({
            "message": "Farmer registered successfully",
            "farmer_id": farmer_profile.id
        }, status=201)
        
    except Exception as e:
        # Catch and surface database rule failures (e.g., duplicated usernames, non-unique phone records).
        return Response({"error": str(e)}, status=400)
    

# view  porters collections list
class MyCollections(generics.ListAPIView):
    serializer_class=MilkCollectionSerializer
    permission_classes=[IsAuthenticated]

    def get_queryset(self):
        porter=self.request.user.porter_profile
        collections=(
            MilkCollection.objects
            .filter(porter=porter)
            .select_related('farmer')
            .order_by('created_at')
        )
        return collections 

#porters notice view
class PorterNoticeView(generics.ListAPIView):
    serializer_class=NoticeSerializer
    permission_classes=[IsAuthenticated]

    def get_queryset(self):
        notices=(
            Notice.objects
            .filter(target__in=['ALL','PORTERS'])
            .order_by('-created_at')
        )
        return notices
    
#farmers notice view
class FarmerNoticeView(generics.ListAPIView):
         serializer_class=NoticeSerializer
         permission_classes=[IsAuthenticated]

         def get_queryset(self):
             notices=(
                Notice.objects
                .filter(target__in=['ALL','FARMERS'])
                .order_by('-created_at') 
             )
             return notices


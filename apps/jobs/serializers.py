from rest_framework import serializers
from django.db.models import Avg
from .models import Job, JobApplication, Rating
from apps.users.models import User


class EmployerBriefSerializer(serializers.ModelSerializer):
    avg_rating = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'phone', 'business_name', 'avg_rating']

    def get_avg_rating(self, obj):
        avg = obj.ratings_received.aggregate(avg=Avg('stars'))['avg']
        return round(avg, 1) if avg else None


class JobListSerializer(serializers.ModelSerializer):
    """Used in the job feed — includes match score injected externally."""
    employer = EmployerBriefSerializer(read_only=True)
    match_score = serializers.FloatField(read_only=True, default=0)
    distance_km = serializers.FloatField(read_only=True, default=0)
    employer_rating = serializers.FloatField(read_only=True, allow_null=True)

    class Meta:
        model = Job
        fields = [
            'id', 'title', 'skill_required', 'location_area', 'location_city',
            'pay_per_worker', 'duration_hours', 'start_time',
            'status', 'escrow_funded',
            'employer', 'match_score', 'distance_km', 'employer_rating',
            'created_at',
        ]


class JobCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = [
            'title', 'description', 'skill_required', 'workers_needed',
            'location_area', 'location_city', 'location_lat', 'location_lng',
            'pay_per_worker', 'duration_hours', 'start_time',
            'source_channel',
        ]

    def create(self, validated_data):
        employer = self.context['request'].user
        return Job.objects.create(employer=employer, **validated_data)


class JobDetailSerializer(serializers.ModelSerializer):
    employer = EmployerBriefSerializer(read_only=True)
    applications_count = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = '__all__'

    def get_applications_count(self, obj):
        return obj.applications.count()


class JobApplicationSerializer(serializers.ModelSerializer):
    worker_phone = serializers.CharField(source='worker.phone', read_only=True)
    worker_name = serializers.CharField(source='worker.full_name', read_only=True)
    job_title = serializers.CharField(source='job.title', read_only=True)
    pay = serializers.DecimalField(source='job.pay_per_worker', max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = JobApplication
        fields = [
            'id', 'job', 'job_title', 'pay',
            'worker_phone', 'worker_name',
            'status', 'accepted_at', 'completed_at',
        ]


class RatingCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rating
        fields = ['to_user', 'job', 'stars', 'comment']

    def validate_stars(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError('Stars must be between 1 and 5.')
        return value

    def validate(self, data):
        request = self.context['request']
        if data['to_user'] == request.user:
            raise serializers.ValidationError('You cannot rate yourself.')
        # Ensure the job involves both users
        job = data['job']
        from_user = request.user
        if from_user.role == 'worker':
            if job.employer != data['to_user']:
                raise serializers.ValidationError('You can only rate the employer of your job.')
        else:
            apps = job.applications.filter(worker=data['to_user'])
            if not apps.exists():
                raise serializers.ValidationError('You can only rate workers on your jobs.')
        return data

    def create(self, validated_data):
        return Rating.objects.create(
            from_user=self.context['request'].user,
            **validated_data
        )


class RatingListSerializer(serializers.ModelSerializer):
    from_name = serializers.CharField(source='from_user.full_name', read_only=True)

    class Meta:
        model = Rating
        fields = ['id', 'from_name', 'stars', 'comment', 'created_at']
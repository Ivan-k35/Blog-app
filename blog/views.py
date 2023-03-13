from django.shortcuts import render, get_object_or_404
from django.core.mail import send_mail
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models import Count
from django.views.decorators.http import require_POST
from django.contrib.postgres.search import SearchVector, SearchRank, SearchQuery
# from django.views.generic import ListView

from taggit.models import Tag
from .models import Post
from .forms import EmailPostForm, CommentForm, SearchForm


# class PostListView(ListView):
#     """
#     Alternative post_list view
#     """
#     queryset = Post.published.all()
#     context_object_name = 'posts'
#     paginate_by = 3
#     template_name = 'blog/post/list.html'


def post_list(request, tag_slug=None):
    list_of_posts = Post.published.all()
    tag = None
    if tag_slug:
        tag = get_object_or_404(Tag, slug=tag_slug)
        list_of_posts = list_of_posts.filter(tags__in=[tag])
    # Pagination with 3 posts per page
    paginator = Paginator(list_of_posts, 3)
    page_number = request.GET.get('page', 1)

    try:
        posts = paginator.page(page_number)
    except PageNotAnInteger:
        # If page_number is not an integer deliver the first page
        posts = paginator.page(1)
    except EmptyPage:
        # If page_number is out of range deliver last page of results
        posts = paginator.page(paginator.num_pages)
    context = {'posts': posts, 'tag': tag}

    return render(request, 'blog/post/list.html', context)


def post_detail(request, year, month, day, post):
    post = get_object_or_404(Post,
                             status=Post.Status.PUBLISHED,
                             slug=post,
                             publish__year=year,
                             publish__month=month,
                             publish__day=day)
    # List of active comments for this post
    comments = post.comments.filter(active=True)
    # Form for users comment
    form = CommentForm()

    # List of similar posts
    post_tags_ids = post.tags.values_list('id', flat=True)
    similar_post = Post.published.filter(tags__in=post_tags_ids).exclude(pk=post.pk)
    similar_post = similar_post.annotate(same_tags=Count('tags')).order_by('-same_tags', '-publish')[0:4]

    context = {'post': post, 'comments': comments, 'form': form, 'similar_post': similar_post}
    return render(request, 'blog/post/detail.html', context)


def post_share(request, post_id):
    # Retrieve post by id
    post = get_object_or_404(Post, pk=post_id, status=Post.Status.PUBLISHED)
    sent = False

    if request.method == 'POST':
        # Form was submitted
        form = EmailPostForm(request.POST)
        if form.is_valid():
            # Form fields passed validation
            cd = form.cleaned_data
            post_url = request.build_absolute_uri(post.get_absolute_url())
            subject = f"{cd['name']} recommends you read {post.title}"
            message = f"Read {post.title} at {post_url} \n\n" \
                      f"{cd['name']}'s comments: {cd['comments']}"
            send_mail(subject, message, 'testuser3535test@gmail.com', [cd['to']])
            sent = True
    else:
        form = EmailPostForm()
    context = {'post': post, 'form': form, 'sent': sent}
    return render(request, 'blog/post/share.html', context)


@require_POST
def post_comment(request, post_id):
    post = get_object_or_404(Post, pk=post_id, status=Post.Status.PUBLISHED)
    comment = None
    # A comment was posted
    form = CommentForm(data=request.POST)
    if form.is_valid():
        # Create a Comment object without saving it to the database
        comment = form.save(commit=False)
        # Assign the post to the comment
        comment.post = post
        # Save the comment to the database
        comment.save()
    context = {'post': post, 'form': form, 'comment': comment}
    return render(request, 'blog/post/comment.html', context)


def post_search(request):
    form = SearchForm()
    query = None
    results = []

    if 'query' in request.GET:
        form = SearchForm(request.GET)
        if form.is_valid():
            query = form.cleaned_data['query']
            search_vector = SearchVector('title', weight='A') + SearchVector('body', weight='B')
            search_query = SearchQuery(query)
            results = Post.published.annotate(
                search=search_vector, rank=SearchRank(search_vector, search_query)
            ).filter(rank__gte=0.3).order_by('-rank')

    context = {'form': form, 'query': query, 'results': results}
    return render(request, 'blog/post/search.html', context)

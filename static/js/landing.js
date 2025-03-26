/**
 * landing.js - JavaScript for Hospital Transport System landing page
 * Provides animations, interactions and visual effects
 */

// Initialize when document is ready
document.addEventListener('DOMContentLoaded', function() {
  // Initialize animations
  initAnimations();

  // Create particle effect in hero section
  createParticles();

  // Initialize smooth scrolling for navigation
  initSmoothScroll();

  // Add scroll-triggered animations
  initScrollEffects();
});

/**
 * Initialize entrance animations
 */
function initAnimations() {
  // Hero content fade in
  const heroContent = document.querySelector('.hero-content');
  setTimeout(() => {
    heroContent.style.opacity = 1;
    heroContent.style.transform = 'translateY(0)';
  }, 200);

  // Staggered tool cards animation
  const toolCards = document.querySelectorAll('.tool-card');
  toolCards.forEach((card, index) => {
    setTimeout(() => {
      card.classList.add('aos-animate');
    }, 300 + (index * 150));
  });
}

/**
 * Create particle effect in hero background
 */
function createParticles() {
  const particlesContainer = document.querySelector('.hero-particles');
  if (!particlesContainer) return;

  // Create 50 particle elements
  for (let i = 0; i < 50; i++) {
    createParticle(particlesContainer);
  }
}

/**
 * Create a single floating particle
 */
function createParticle(container) {
  // Create particle element
  const particle = document.createElement('div');
  particle.className = 'particle';

  // Set random properties
  const size = Math.random() * 5 + 2;
  const posX = Math.random() * 100;
  const posY = Math.random() * 100;
  const opacity = Math.random() * 0.5 + 0.1;
  const duration = Math.random() * 20 + 10;
  const delay = Math.random() * 5;

  // Apply styles
  particle.style.cssText = `
    position: absolute;
    width: ${size}px;
    height: ${size}px;
    border-radius: 50%;
    background-color: rgba(255, 255, 255, ${opacity});
    left: ${posX}%;
    top: ${posY}%;
    animation: float ${duration}s infinite ease-in-out ${delay}s;
  `;

  // Add to container
  container.appendChild(particle);
}

/**
 * Initialize smooth scrolling for navigation links
 */
function initSmoothScroll() {
  const links = document.querySelectorAll('a[href^="#"]');

  links.forEach(link => {
    link.addEventListener('click', function(e) {
      e.preventDefault();

      const targetId = this.getAttribute('href');
      if (targetId === '#') return;

      const targetElement = document.querySelector(targetId);
      if (!targetElement) return;

      window.scrollTo({
        top: targetElement.offsetTop - 60,
        behavior: 'smooth'
      });
    });
  });
}

/**
 * Initialize scroll-triggered animations
 */
function initScrollEffects() {
  // Get all elements with data-aos attribute
  const animatedElements = document.querySelectorAll('[data-aos]');

  // Create IntersectionObserver
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('aos-animate');
        // Unobserve after animating to improve performance
        observer.unobserve(entry.target);
      }
    });
  }, {
    threshold: 0.1, // Trigger when 10% of element is visible
    rootMargin: '0px 0px -100px 0px' // Adjust trigger point
  });

  // Observe all animated elements
  animatedElements.forEach(element => {
    observer.observe(element);
  });

  // Animate features on scroll
  animateOnScroll('.feature-item', 'feature-item--visible', 0.2, 150);

  // Add parallax effect to info section
  initParallaxEffect();
}

/**
 * Animate elements with staggered delay on scroll
 */
function animateOnScroll(selector, activeClass, threshold, staggerDelay) {
  const elements = document.querySelectorAll(selector);
  if (!elements.length) return;

  const observer = new IntersectionObserver((entries) => {
    let delay = 0;

    entries.forEach(entry => {
      if (entry.isIntersecting) {
        setTimeout(() => {
          entry.target.classList.add(activeClass);
        }, delay);

        delay += staggerDelay;
        observer.unobserve(entry.target);
      }
    });
  }, {
    threshold: threshold || 0.1
  });

  elements.forEach(element => {
    observer.observe(element);
  });
}

/**
 * Initialize parallax scrolling effects
 */
function initParallaxEffect() {
  window.addEventListener('scroll', () => {
    const scrollPosition = window.scrollY;

    // Parallax for hero section
    const heroSection = document.querySelector('.hero');
    if (heroSection) {
      const heroContent = heroSection.querySelector('.hero-content');
      if (heroContent && scrollPosition < window.innerHeight) {
        heroContent.style.transform = `translateY(${scrollPosition * 0.2}px)`;
      }
    }

    // Parallax for info section images
    const infoImage = document.querySelector('.info-image img');
    if (infoImage) {
      const infoSection = document.querySelector('.info');
      const infoOffset = infoSection.offsetTop;
      const scrollRelative = scrollPosition - infoOffset;

      if (scrollRelative > -window.innerHeight && scrollRelative < window.innerHeight) {
        infoImage.style.transform = `scale(1.03) translateY(${scrollRelative * 0.05}px)`;
      }
    }

    // Add rotating effect to tool icons on scroll
    const toolIcons = document.querySelectorAll('.tool-icon');
    toolIcons.forEach(icon => {
      const parentCard = icon.closest('.tool-card');
      if (parentCard) {
        const cardTop = parentCard.getBoundingClientRect().top;
        if (cardTop < window.innerHeight && cardTop > 0) {
          const rotateAmount = (window.innerHeight / 2 - cardTop) * 0.05;
          icon.style.transform = `rotate(${rotateAmount}deg)`;
        }
      }
    });
  });
}

/**
 * Add interactive "tilt" effect to cards on mouse move
 */
function addTiltEffectToCards() {
  const cards = document.querySelectorAll('.tool-card-inner');

  cards.forEach(card => {
    card.addEventListener('mousemove', handleTilt);
    card.addEventListener('mouseleave', resetTilt);
  });

  function handleTilt(e) {
    const cardRect = this.getBoundingClientRect();
    const cardCenterX = cardRect.left + cardRect.width / 2;
    const cardCenterY = cardRect.top + cardRect.height / 2;

    const mouseX = e.clientX - cardCenterX;
    const mouseY = e.clientY - cardCenterY;

    // Calculate tilt angles (max 10 degrees)
    const tiltX = (mouseY / (cardRect.height / 2)) * 10;
    const tiltY = -(mouseX / (cardRect.width / 2)) * 10;

    // Apply transform
    this.style.transform = `perspective(1000px) rotateX(${tiltX}deg) rotateY(${tiltY}deg)`;
  }

  function resetTilt() {
    this.style.transform = 'perspective(1000px) rotateX(0) rotateY(0)';
  }
}

// Create typing animation for CTA section
function createTypingEffect() {
  const ctaHeading = document.querySelector('.cta h2');
  if (!ctaHeading) return;

  const originalText = ctaHeading.textContent;
  ctaHeading.textContent = '';

  let charIndex = 0;

  function typeNextCharacter() {
    if (charIndex < originalText.length) {
      ctaHeading.textContent += originalText.charAt(charIndex);
      charIndex++;
      setTimeout(typeNextCharacter, 50);
    }
  }

  // Start typing when CTA section comes into view
  const observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting) {
      typeNextCharacter();
      observer.disconnect();
    }
  });

  observer.observe(ctaHeading);
}

// Call additional effects with a slight delay to ensure page is rendered
setTimeout(() => {
  addTiltEffectToCards();
  createTypingEffect();
}, 1000);
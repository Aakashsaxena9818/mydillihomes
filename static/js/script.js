<script>
  const hamburger = document.getElementById('hamburger');
  const navMenu = document.getElementById('navMenu');
  const submenuParent = document.querySelector('.has-submenu');

  hamburger.addEventListener('click', () => {
    navMenu.classList.toggle('active');
  });

  submenuParent.addEventListener('click', () => {
    submenuParent.classList.toggle('open');
  });

  // On window resize, reset menu
  window.addEventListener('resize', () => {
    if (window.innerWidth > 768) {
      navMenu.classList.remove('active');
      submenuParent.classList.remove('open');
    }
  });
</script>
